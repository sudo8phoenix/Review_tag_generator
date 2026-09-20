#!/usr/bin/env python3
"""Evaluate normalization on synthetic fixtures or a human-labelled JSONL set.

Synthetic scores are development evidence only; they do not satisfy the human
review quality gate. Semantic tuning runs only when a pinned local model path is
explicitly supplied. No downloads are performed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from review_tag_generator.normalization import (  # noqa: E402
    MINILM_REVISION,
    AspectNormalizer,
    get_ontology,
)

UNKNOWN_TERMS = (
    "hinge durability", "fingerprint reader", "warranty coverage", "bluetooth pairing",
    "wifi reception", "operating system", "software updates", "hinges", "touchscreen pen",
    "screen glare coating", "microphone", "fan noise", "keyboard backlight", "factory reset",
    "return policy", "repair process", "color options", "stylus", "biometric login",
    "accessories included", "firmware", "hinge movement", "customer returns", "bluetooth",
    "wifi", "microphone quality", "noise cancellation", "warranty", "software", "screen hinge",
    "random accessory", "firmware update", "return experience", "fingerprint sensor", "stylus support",
    "wireless connection", "fan sound", "included accessories", "color", "pen input", "repairability",
)
DEV_WRAPPERS = ("{term} quality", "the {term} feature", "my {term} experience", "about {term}")
TEST_WRAPPERS = ("quality of {term}", "this {term} feature", "experience with {term}", "regarding {term}")


def build_synthetic_examples() -> tuple[list[dict], list[dict]]:
    """Create 100 dev and 100 held-out fixture rows with split-specific templates."""
    ontology = get_ontology()
    aspects = list(ontology.aspects)
    dev: list[dict] = []
    heldout: list[dict] = []
    for split, wrappers in ((dev, DEV_WRAPPERS), (heldout, TEST_WRAPPERS)):
        candidates = []
        for aspect in aspects:
            terms = (aspect.display_label, *aspect.aliases)
            paraphrase_term = terms[2] if len(terms) > 2 else terms[-1]
            candidates.append([
                {"text": terms[0], "label": aspect.id},
                {"text": terms[1], "label": aspect.id},
                {"text": wrappers[0].format(term=paraphrase_term), "label": aspect.id},
                {"text": wrappers[1].format(term=terms[-1]), "label": aspect.id},
            ])
        # Three examples per aspect plus 17 distributed extras make exactly 80
        # known rows; exact aliases give a useful alias-only baseline, while the
        # contextual paraphrases exercise optional semantics. These are fixtures,
        # not human-reviewed examples.
        for group in candidates:
            split.extend(group[:3])
        for group in candidates[:17]:
            split.append(group[3])
        offset = 0 if split is dev else 20
        for term in UNKNOWN_TERMS[offset:offset + 20]:
            split.append({"text": term, "label": None})
    return dev, heldout


def load_human_jsonl(path: Path) -> tuple[list[dict], list[dict]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 200:
        raise ValueError(f"human-labelled input must contain exactly 200 rows; got {len(rows)}")
    if any(not isinstance(row.get("text"), str) or "label" not in row for row in rows):
        raise ValueError("each JSONL row requires text and label (canonical ID or null)")
    return rows[:100], rows[100:]


def metrics(rows: list[dict], normalizer: AspectNormalizer) -> dict:
    correct = 0
    false_known = 0
    per_class: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        expected = row["label"]
        result = normalizer.normalize(row["text"], context=row.get("context"))
        actual = result.normalized_aspect_id
        correct += actual == expected
        false_known += expected is None and actual is not None
        key = expected if expected is not None else "unknown"
        per_class[key]["total"] += 1
        per_class[key]["correct"] += actual == expected
    total = len(rows)
    return {
        "accuracy_including_unknowns": correct / total if total else 0.0,
        "false_known_unknown_count": false_known,
        "examples": total,
        "per_class": {
            label: {"correct": count["correct"], "total": count["total"],
                    "recall": count["correct"] / count["total"]}
            for label, count in sorted(per_class.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, help="local all-MiniLM-L6-v2 snapshot; never downloaded")
    parser.add_argument("--revision", default=MINILM_REVISION)
    parser.add_argument("--examples-jsonl", type=Path, help="200 human-reviewed rows, dev first then held-out")
    parser.add_argument("--output", type=Path, help="write JSON report (default stdout)")
    args = parser.parse_args()

    if args.examples_jsonl:
        dev, heldout = load_human_jsonl(args.examples_jsonl)
        data_status = "human-labelled; reviewer provenance must be recorded by the caller"
    else:
        dev, heldout = build_synthetic_examples()
        data_status = "synthetic fixtures; quality gate pending human review"

    report: dict = {
        "ontology_version": get_ontology().version,
        "dataset_status": data_status,
        "development_examples": len(dev),
        "heldout_examples": len(heldout),
        "quality_gate": "pending human review" if not args.examples_jsonl else "eligible for review, not automatically passed",
        "semantic_model": None,
    }
    if args.model_path is None:
        alias_only = AspectNormalizer()
        report["mode"] = "alias-only (semantic matching explicitly disabled)"
        report["alias_only"] = {"development": metrics(dev, alias_only), "heldout": metrics(heldout, alias_only)}
        report["threshold_tuning"] = "not run: no local semantic model supplied"
    else:
        if args.revision != MINILM_REVISION:
            raise ValueError(f"revision must equal pinned revision {MINILM_REVISION}")
        candidates = [round(0.50 + 0.02 * i, 2) for i in range(21)]
        tuned = []
        for threshold in candidates:
            normalizer = AspectNormalizer(
                semantic_model_path=args.model_path,
                semantic_revision=args.revision,
                threshold=threshold,
            )
            result = metrics(dev, normalizer)
            tuned.append((result["accuracy_including_unknowns"], -result["false_known_unknown_count"], threshold, result))
        # Highest accuracy, then fewer false-known unknowns, then the higher threshold.
        _, _, threshold, dev_metrics = max(tuned, key=lambda row: (row[0], row[1], row[2]))
        normalizer = AspectNormalizer(
            semantic_model_path=args.model_path,
            semantic_revision=args.revision,
            threshold=threshold,
        )
        report["mode"] = "semantic + alias"
        report["semantic_model"] = {"id": "sentence-transformers/all-MiniLM-L6-v2", "revision": args.revision}
        report["threshold_tuning"] = {"candidates": candidates, "selected": threshold, "tie_policy": "accuracy, fewer false-known unknowns, higher threshold"}
        report["development"] = dev_metrics
        report["heldout"] = metrics(heldout, normalizer)
        if not args.examples_jsonl:
            report["quality_gate"] = "pending human review; synthetic held-out score is not a gold claim"

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
