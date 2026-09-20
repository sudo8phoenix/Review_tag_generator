"""Reproduce Kaggle evidence and evaluate the frozen local inference policy.

Run validation first. The test command refuses to run until the validation
decision has been written and refuses to overwrite an existing test report.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from review_tag_generator.artifacts import verify_checkpoint  # noqa: E402
from review_tag_generator.transformer_models import TransformerModels  # noqa: E402

LABELS = ("negative", "neutral", "positive")
LABEL_IDS = {label: index for index, label in enumerate(LABELS)}
PROCESSED = ROOT / "data/processed/distilbert"
EVIDENCE = ROOT / "audit/evidence"
CURRENT = EVIDENCE / "current"
ASPECT_PATH = ROOT / "models/aspect_extractor/distilbert_weighted_lr3e5/best"
SENTIMENT_PATH = ROOT / "models/sentiment_classifier/distilbert/best"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def representation_hash(value: object) -> str:
    """Notebook sha256_text(json.dumps(value, sort_keys=True))."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def load_reviews(split: str) -> list[dict]:
    with (PROCESSED / f"{split}.jsonl").open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def build_pairs(reviews: list[dict]) -> list[dict]:
    """Notebook build_sentiment_pairs, including its deduplication key/order."""
    pairs = []
    seen = set()
    for review in reviews:
        for ann in review["annotations"]:
            key = (review["review_id"], ann["start_char"], ann["end_char"], ann["sentiment"])
            if key in seen:
                continue
            seen.add(key)
            pairs.append({
                "review_id": review["review_id"],
                "product_id": review["product_id"],
                "review_text": review["review_text"],
                "aspect_text": ann["aspect"],
                "start_char": ann["start_char"],
                "end_char": ann["end_char"],
                "label": ann["sentiment"],
                "label_id": LABEL_IDS[ann["sentiment"]],
            })
    return pairs


def split_hashes(split: str, reviews: list[dict], pairs: list[dict]) -> dict:
    a2_manifest = json.loads((EVIDENCE / "A2/aspect_training_manifest.json").read_text())
    a3_manifest = json.loads((EVIDENCE / "A3/sentiment_training_manifest.json").read_text())
    a2_hash = representation_hash(reviews)
    a3_hash = representation_hash(pairs)
    expected_a2 = a2_manifest["dataset_hashes"][split]
    expected_a3 = a3_manifest["dataset_hashes"][split]
    if (a2_hash, a3_hash) != (expected_a2, expected_a3):
        raise RuntimeError(f"{split}: processed representation differs from Kaggle manifests")
    return {
        "review_count": len(reviews),
        "sentiment_pair_count": len(pairs),
        "file_sha256": sha256_file(PROCESSED / f"{split}.jsonl"),
        "a2_review_list_sha256": a2_hash,
        "a3_deduplicated_pair_list_sha256": a3_hash,
        "matches_kaggle_manifests": True,
    }


def classification_metrics(matrix: list[list[int]], labels: tuple[str, ...] = LABELS) -> dict:
    if len(matrix) != len(labels) or any(len(row) != len(labels) or any(v < 0 for v in row) for row in matrix):
        raise ValueError("Confusion matrix must be square with nonnegative counts")
    total = sum(map(sum, matrix))
    classes = {}
    for i, label in enumerate(labels):
        tp = matrix[i][i]
        support = sum(matrix[i])
        predicted = sum(row[i] for row in matrix)
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        classes[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    return {
        "n": total,
        "accuracy": sum(matrix[i][i] for i in range(len(labels))) / total if total else 0.0,
        "macro_precision": sum(c["precision"] for c in classes.values()) / len(labels),
        "macro_recall": sum(c["recall"] for c in classes.values()) / len(labels),
        "macro_f1": sum(c["f1"] for c in classes.values()) / len(labels),
        "per_class": classes,
        "labels": list(labels),
        "confusion_matrix": matrix,
    }


def metrics_from_labels(gold: list[str], predicted: list[str]) -> dict:
    if len(gold) != len(predicted):
        raise ValueError("Gold and prediction counts differ")
    matrix = [[0 for _ in LABELS] for _ in LABELS]
    for actual, output in zip(gold, predicted):
        matrix[LABEL_IDS[actual]][LABEL_IDS[output]] += 1
    return classification_metrics(matrix)


def span_metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def select_policy(scores: dict[str, dict]) -> dict:
    eligible = [name for name in ("full_review", "local_clause")
                if all(scores[name]["per_class"][label]["recall"] >= 0.5 for label in LABELS)]
    if not eligible:
        return {"policy": None, "reason": "Neither policy meets all-class recall >= 0.50"}
    if len(eligible) == 1:
        return {"policy": eligible[0], "reason": "Only eligible policy"}
    full = scores["full_review"]["macro_f1"]
    local = scores["local_clause"]["macro_f1"]
    if abs(full - local) <= 0.001:
        return {"policy": "full_review", "reason": "Macro F1 tie within 0.001"}
    return {"policy": "full_review" if full > local else "local_clause", "reason": "Higher validation Macro F1"}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_models(policy: str = "full_review") -> TransformerModels:
    verify_checkpoint(ASPECT_PATH, EVIDENCE / "A2/aspect_training_manifest.json", "aspect")
    verify_checkpoint(SENTIMENT_PATH, EVIDENCE / "A3/sentiment_training_manifest.json", "sentiment")
    return TransformerModels(ASPECT_PATH, SENTIMENT_PATH, device="cpu", context_policy=policy)


def predict_historical(models: TransformerModels, pair: dict) -> str:
    """Notebook tokenizer(review, aspect, truncation='only_first', max_length=256)."""
    encoded = models.sentiment_tokenizer(pair["review_text"], pair["aspect_text"],
                                         truncation="only_first", max_length=256, return_tensors="pt")
    with models.torch.inference_mode():
        logits = models.sentiment_model(**encoded).logits[0]
    return models.sentiment_model.config.id2label[int(logits.argmax())].lower()


def predict_policy(models: TransformerModels, pair: dict, policy: str) -> str:
    models.context_policy = policy
    return models.predict_sentiment(pair["review_text"], pair["aspect_text"],
                                    pair["start_char"], pair["end_char"]).label.value


def evaluate_sentiment(models: TransformerModels, pairs: list[dict], protocols: tuple[str, ...]) -> dict:
    gold = [pair["label"] for pair in pairs]
    predictions = {name: [] for name in protocols}
    for index, pair in enumerate(pairs, 1):
        for name in protocols:
            output = predict_historical(models, pair) if name == "notebook_full_review" else predict_policy(models, pair, name)
            predictions[name].append(output)
        if index % 100 == 0:
            print(f"sentiment: {index}/{len(pairs)}", flush=True)
    result = {}
    for name in protocols:
        result[name] = metrics_from_labels(gold, predictions[name])
        result[name]["error_count"] = sum(a != b for a, b in zip(gold, predictions[name]))
        result[name]["error_categories"] = {f"{actual}_to_{output}": count for (actual, output), count in
                                              sorted(Counter((a, b) for a, b in zip(gold, predictions[name]) if a != b).items())}
    return result


def evaluate_aspects(models: TransformerModels, reviews: list[dict]) -> dict:
    tp = fp = fn = 0
    review_errors = 0
    for index, review in enumerate(reviews, 1):
        gold = {(a["start_char"], a["end_char"], a["aspect"].lower()) for a in review["annotations"]}
        predicted = {(p.start_char, p.end_char, p.aspect.lower()) for p in models.extract_aspects(review["review_text"])}
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        review_errors += gold != predicted
        if index % 100 == 0:
            print(f"aspects: {index}/{len(reviews)}", flush=True)
    return {"protocol": "current_windowed_extraction_exact_offsets_and_lowercase_text",
            "review_count": len(reviews), "review_error_count": review_errors, "exact_span": span_metrics(tp, fp, fn)}


def historical_derivative() -> dict:
    path = EVIDENCE / "A3/sentiment_confusion_matrix.json"
    original = json.loads(path.read_text())
    matrix = original["matrix"]
    # Notebook created the matrix with numeric labels [0,1,2], mapped as below.
    historical = json.loads((EVIDENCE / "A3/sentiment_test.json").read_text())
    corrected = classification_metrics(matrix)
    for label in LABELS:
        if abs(corrected["per_class"][label]["recall"] - historical["per_class_recall"][label]) > 1e-12:
            raise RuntimeError("Historical confusion matrix does not support inferred label order")
    return {"source": str(path.relative_to(ROOT)), "source_file_sha256": sha256_file(path),
            "source_claimed_labels": original["labels"], "correct_labels": list(LABELS),
            "row_axis": "gold", "column_axis": "predicted", "metrics": corrected,
            "derivation": "Notebook confusion_matrix(test_true, test_predictions, labels=[0,1,2]); ID map 0=negative, 1=neutral, 2=positive. Original export mislabeled rows/columns."}


def hash_inventory() -> dict:
    inventory = {}
    for split in ("train", "validation", "test"):
        reviews = load_reviews(split)
        inventory[split] = split_hashes(split, reviews, build_pairs(reviews))
    return {"algorithms": {"file_sha256": "SHA-256 over JSONL file bytes",
                           "a2_review_list_sha256": "SHA-256 of UTF-8 json.dumps(list of notebook Review.model_dump(mode='json'), sort_keys=True)",
                           "a3_deduplicated_pair_list_sha256": "SHA-256 of UTF-8 json.dumps(notebook build_sentiment_pairs result, sort_keys=True)"},
            "splits": inventory}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("validation", "test", "repeat-validation"))
    args = parser.parse_args(argv)
    # Check the held-out freeze boundary before touching any evidence. In
    # particular, a refused second test invocation must be a read-only no-op.
    if args.phase == "validation" and (CURRENT / "test.json").exists():
        raise RuntimeError("Test report exists; validation decision is frozen")
    if args.phase == "test" and (CURRENT / "test.json").exists():
        raise RuntimeError("Held-out test was already evaluated; refusing to overwrite")
    CURRENT.mkdir(parents=True, exist_ok=True)
    inventory = hash_inventory()
    write_json(CURRENT / "split_hashes.json", inventory)
    write_json(CURRENT / "historical_a3_confusion_corrected.json", historical_derivative())
    if args.phase == "repeat-validation":
        saved = json.loads((CURRENT / "validation.json").read_text())
        models = load_models()
        repeated = evaluate_sentiment(models, build_pairs(load_reviews("validation")),
                                      ("full_review", "local_clause"))
        if repeated != saved["policies"]:
            raise RuntimeError("Repeated validation predictions differ from frozen report")
        print("VALIDATION REPEAT: exact metrics and confusion matrices match")
        return 0
    if args.phase == "validation":
        reviews = load_reviews("validation")
        models = load_models()
        scores = evaluate_sentiment(models, build_pairs(reviews), ("full_review", "local_clause"))
        decision = select_policy(scores)
        report = {"split": "validation", "protocol": "gold_aspect_pairs_current_inference",
                  "split_hashes": inventory["splits"]["validation"], "policies": scores,
                  "selection": decision, "checkpoint_hashes": {
                      "aspect": json.loads((EVIDENCE / "A2/aspect_training_manifest.json").read_text())["checkpoint"]["sha256"],
                      "sentiment": json.loads((EVIDENCE / "A3/sentiment_training_manifest.json").read_text())["checkpoint"]["sha256"]}}
        write_json(CURRENT / "validation.json", report)
        if decision["policy"] is None:
            print("BLOCKED: neither validation policy meets recall threshold")
            return 2
        write_json(CURRENT / "policy.json", {"selected": decision["policy"], "reason": decision["reason"],
                     "validation_file_sha256": sha256_file(CURRENT / "validation.json"),
                     "settings": {"max_length": 256, "device": "cpu", "extraction_stride": 64,
                                  "max_review_tokens": 4096}})
        print(f"FROZEN POLICY: {decision['policy']}")
        return 0
    policy_path = CURRENT / "policy.json"
    if not policy_path.exists():
        raise RuntimeError("Run validation and freeze policy before held-out test")
    frozen = json.loads(policy_path.read_text())
    if sha256_file(CURRENT / "validation.json") != frozen["validation_file_sha256"]:
        raise RuntimeError("Validation report changed after policy freeze")
    reviews = load_reviews("test")
    models = load_models(frozen["selected"])
    protocols = ("notebook_full_review", frozen["selected"])
    scores = evaluate_sentiment(models, build_pairs(reviews), protocols)
    aspects = evaluate_aspects(models, reviews)
    historical = json.loads((EVIDENCE / "A3/sentiment_test.json").read_text())
    historical_matrix = historical["confusion_matrix"]
    parity = scores["notebook_full_review"]["confusion_matrix"] == historical_matrix
    baseline_a3 = 0.6173789003975411  # Kaggle A3 gate claim; no baseline model shipped.
    baseline_a2 = 0.36719286204529855  # Kaggle A2 gate claim.
    current_a3 = scores[frozen["selected"]]
    gates = {"a2_exact_span_f1_at_least_0_70": aspects["exact_span"]["f1"] >= 0.70,
             "a2_above_historical_rule_baseline": aspects["exact_span"]["f1"] > baseline_a2,
             "a3_macro_f1_at_least_0_65": current_a3["macro_f1"] >= 0.65,
             "a3_all_class_recall_at_least_0_50": all(current_a3["per_class"][x]["recall"] >= 0.5 for x in LABELS),
             "a3_above_historical_tfidf_baseline": current_a3["macro_f1"] > baseline_a3}
    report = {"split": "test", "held_out_evaluations": 1, "policy_frozen_before_test": frozen,
              "split_hashes": inventory["splits"]["test"], "protocols": scores, "aspect_extraction": aspects,
              "historical_parity": {"confusion_matrix_equal": parity,
                                    "historical_macro_f1": historical["macro_f1"],
                                    "reproduced_macro_f1": scores["notebook_full_review"]["macro_f1"]},
              "historical_baselines_reported_not_retrained": {"a2_rule_exact_span_f1": baseline_a2,
                                                               "a3_tfidf_macro_f1": baseline_a3},
              "gates": gates, "status": "PASS" if all(gates.values()) and parity else "BLOCKED"}
    write_json(CURRENT / "test.json", report)
    print(f"TEST STATUS: {report['status']}; notebook parity: {parity}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
