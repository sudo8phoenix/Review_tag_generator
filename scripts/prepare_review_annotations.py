#!/usr/bin/env python3
"""Download and prepare an independent electronics annotation workset.

Source labels are review-level metadata. They never become mention-level gold.
Raw reviews and annotation worksets stay under ignored data/ directories.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATASET_URL = "https://data.mendeley.com/datasets/d5vsgcxrk5/1"
DOWNLOAD_URL = (
    "https://data.mendeley.com/public-files/datasets/d5vsgcxrk5/files/"
    "da1b0c98-30c0-4d45-a87d-5edcec234ac8/file_downloaded"
)
SOURCE_SHA256 = "7625ec57846d671f21de8c4df69c4e348e04864eaac378d8cb2a3353d661480d"
DEFAULT_SOURCE = ROOT / "data/raw/virtual_assistant_devices/devices-v1.xlsx"
DEFAULT_OUTPUT = ROOT / "data/annotations/virtual-assistant-v1"
SENTIMENTS = {"positive", "neutral", "negative"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", normalized)) or normalized.strip()


def download_source(path: Path) -> None:
    if path.exists():
        if digest(path.read_bytes()) != SOURCE_SHA256:
            raise ValueError("Existing source differs from the publisher hash; refusing overwrite")
        return
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "ReviewTagGenerator/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000 or digest(content) != SOURCE_SHA256:
        raise ValueError("Download size or publisher SHA-256 verification failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        # Exclusive creation prevents replacing another process's source.
        os.link(temporary, path)
    finally:
        temporary.unlink()


def read_source(path: Path) -> list[dict]:
    """Read this version's fixed worksheet schema without executing formulas."""
    if digest(path.read_bytes()) != SOURCE_SHA256:
        raise ValueError("Workbook does not match the pinned publisher SHA-256")
    with zipfile.ZipFile(path) as archive:
        strings = [
            "".join(node.text or "" for node in item.findall(".//m:t", NS))
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))
        ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    source_rows = sheet.findall("m:sheetData/m:row", NS)
    rows = []
    metadata = {}
    for source_row in source_rows:
        cells = {}
        for cell in source_row:
            if cell.find("m:f", NS) is not None:
                raise ValueError("Unexpected formula in source workbook")
            value = cell.find("m:v", NS)
            text = value.text if value is not None else ""
            if cell.get("t") == "s":
                text = strings[int(text)]
            elif cell.get("t") == "inlineStr":
                text = "".join(n.text or "" for n in cell.findall(".//m:t", NS))
            cells[re.sub(r"\d", "", cell.attrib["r"])] = text or ""
        number = int(source_row.attrib["r"])
        if number == 1:
            if cells.get("F") != "Sentiment" or cells.get("G") != "Aspect(s)":
                raise ValueError("Unexpected source column layout")
            continue
        for column in ("A", "B", "C"):
            if cells.get(column):
                metadata[column] = cells[column]
        text = cells.get("E", "")
        sentiment = cells.get("F", "").strip().casefold()
        if not text.strip() or sentiment not in SENTIMENTS:
            raise ValueError(f"Missing review or invalid sentiment at worksheet row {number}")
        rows.append({
            "source_row": number,
            "review_text": text,
            "device": metadata.get("A"),
            "company": metadata.get("B"),
            "website": metadata.get("C"),
            "title": cells.get("D", ""),
            "source_review_sentiment": sentiment,
            "source_aspect_categories": [cells[c] for c in ("G", "H", "I", "J", "K") if cells.get(c)],
        })
    return rows


def audit_existing(processed: Path) -> tuple[dict[str, set[str]], dict]:
    index = defaultdict(set)
    evidence = {}
    for split in ("train", "validation", "test"):
        path = processed / f"{split}.jsonl"
        # A missing split must not be mistaken for evidence of independence.
        content = path.read_bytes()
        reviews = [json.loads(line) for line in content.decode().splitlines() if line.strip()]
        for review in reviews:
            index[text_key(review["review_text"])].add(split)
        evidence[split] = {"sha256": digest(content), "reviews": len(reviews)}
    return index, evidence


def build_workset(rows: list[dict], existing: dict[str, set[str]], per_split: int) -> tuple[list[dict], list[dict], dict]:
    if per_split < 1:
        raise ValueError("per_split must be positive")
    groups = defaultdict(list)
    for row in rows:
        groups[text_key(row["review_text"])].append(row)
    candidates = []
    overlaps = Counter()
    conflicting = 0
    for key, members in groups.items():
        labels = {row["source_review_sentiment"] for row in members}
        if len(labels) > 1:
            conflicting += 1
        if key in existing:
            overlaps.update(existing[key])
        if key in existing or len(labels) > 1:
            continue
        representative = min(members, key=lambda row: row["source_row"])
        candidates.append({
            "review_id": "vad1-" + digest(key.encode()),
            **representative,
            "source_rows": sorted(row["source_row"] for row in members),
            "duplicate_group_size": len(members),
        })
    strata = defaultdict(list)
    for row in candidates:
        strata[row["source_review_sentiment"]].append(row)
    for pool in strata.values():
        pool.sort(key=lambda row: digest(("annotation-v1:" + row["review_id"]).encode()))
    selected = []
    positions = Counter()
    labels = sorted(SENTIMENTS)
    # Interleave splits within each class so each gets approximately equal
    # support. Selection never depends on model predictions or confidence.
    for position in range(per_split):
        label = labels[position % len(labels)]
        for split in ("development", "heldout"):
            if positions[label] >= len(strata[label]):
                raise ValueError(f"Insufficient eligible {label} groups for the requested sample")
            row = strata[label][positions[label]]
            positions[label] += 1
            selected.append({
                **row, "split": split,
                "annotation": {"status": "pending", "reviewer": None, "notes": "", "mentions": []},
            })
    summary = {
        "source_rows": len(rows), "unique_normalized_text_groups": len(groups),
        "duplicate_rows": len(rows) - len(groups),
        "conflicting_sentiment_groups": conflicting,
        "overlapping_groups_by_existing_split": dict(sorted(overlaps.items())),
        "eligible_groups": len(candidates),
        "source_sentiment_counts": dict(sorted(Counter(r["source_review_sentiment"] for r in rows).items())),
        "selected_counts": {split: dict(sorted(Counter(r["source_review_sentiment"] for r in selected if r["split"] == split).items())) for split in ("development", "heldout")},
    }
    return candidates, selected, summary


def write_jsonl(path: Path, rows: list[dict]) -> str:
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")
    return digest(content.encode())


def prepare(source: Path, output: Path, processed: Path, per_split: int) -> dict:
    if output.exists():
        raise ValueError("Workset already exists; use a new output directory to preserve annotations")
    rows = read_source(source)
    existing, old_evidence = audit_existing(processed)
    candidates, tasks, summary = build_workset(rows, existing, per_split)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".annotations-", dir=output.parent))
    try:
        files = {"eligible-reviews.jsonl": write_jsonl(stage / "eligible-reviews.jsonl", candidates)}
        for split in ("development", "heldout"):
            name = split + ".jsonl"
            files[name] = write_jsonl(stage / name, [r for r in tasks if r["split"] == split])
        manifest = {
            "dataset": "Virtual Assistant Devices Dataset", "version": 1,
            "doi": "10.17632/d5vsgcxrk5.1", "source_url": DATASET_URL,
            "authors": ["Yaser alhasawi", "Salem Algamdi"],
            "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "download_url": DOWNLOAD_URL, "source_sha256": SOURCE_SHA256,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "source_labels": "Review-level sentiment and categories; no gold spans or per-mention sentiment",
            "quality_gate": "pending independent human span, canonical-ID and sentiment annotation",
            "overlap_method": "NFKC, casefold, Unicode word tokens; punctuation/whitespace ignored. Not a semantic near-duplicate audit.",
            "selection": "Fixed hash order within source-sentiment strata; normalized duplicate groups kept together; overlaps and sentiment-conflict groups excluded",
            "existing_splits": old_evidence, "counts": summary, "files": files,
            "limitations": [
                "Smart assistant domain differs from laptops; this sample is not representative of all electronics.",
                "Source workbook sentiment counts differ from the publisher description; original labels retained.",
                "Source categories are not canonical ontology IDs and must be independently adjudicated.",
                "Model-generated suggestions are not human annotations. Held-out predictions are not generated by this tool.",
            ],
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        stage.rename(output)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def load_tasks(workset: Path, split: str) -> list[dict]:
    manifest = json.loads((workset / "manifest.json").read_text())
    name = split + ".jsonl"
    content = (workset / name).read_bytes()
    if digest(content) != manifest["files"][name]:
        raise ValueError("Original task file has changed; put corrections in a separate reviewed JSONL")
    return [json.loads(line) for line in content.decode().splitlines() if line.strip()]


def validate_annotations(originals: list[dict], corrected: list[dict]) -> dict:
    from review_tag_generator.ontology import get_ontology

    canonical_ids = {a.id for a in get_ontology().aspects}
    reference = {row["review_id"]: row for row in originals}
    if len(corrected) != len(reference) or len({r["review_id"] for r in corrected}) != len(reference):
        raise ValueError("Reviewed file must contain each original task exactly once")
    approved = 0
    for row in corrected:
        base = reference.get(row["review_id"])
        if base is None or {k: v for k, v in row.items() if k != "annotation"} != {k: v for k, v in base.items() if k != "annotation"}:
            raise ValueError("Source text, split and metadata must remain unchanged")
        annotation = row["annotation"]
        if annotation.get("status") not in {"pending", "approved"}:
            raise ValueError("Annotation status must be pending or approved")
        is_approved = annotation["status"] == "approved"
        if is_approved and annotation.get("review_method") == "automated":
            raise ValueError("Automated proposals require independent human review before approval")
        if is_approved and (not isinstance(annotation.get("reviewer"), str) or not annotation["reviewer"].strip()):
            raise ValueError("Approved annotations need an identified human reviewer")
        mentions = annotation.get("mentions")
        if not isinstance(mentions, list):
            raise ValueError("Approved annotations require a mentions list (empty only if no explicit aspects)")
        seen = set()
        for mention in mentions:
            start, end = mention.get("start_char"), mention.get("end_char")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(row["review_text"]):
                raise ValueError("Mention offsets must select an exact nonempty source span")
            if row["review_text"][start:end] != mention.get("raw_aspect"):
                raise ValueError("Mention text does not match its source offsets")
            if mention.get("sentiment") not in SENTIMENTS:
                raise ValueError("Each mention requires its own positive/neutral/negative sentiment")
            if "canonical_id" not in mention or (mention["canonical_id"] is not None and mention["canonical_id"] not in canonical_ids):
                raise ValueError("Each mention requires a canonical ontology ID, or explicit null for unknown")
            if (start, end) in seen:
                raise ValueError("Duplicate mention span; adjudicate conflicting labels first")
            seen.add((start, end))
        approved += is_approved
    return {"tasks": len(originals), "approved": approved, "pending": len(originals) - approved,
            "quality_gate": "annotation complete; independent adjudication still required" if approved == len(originals) else "pending human annotation"}


def build_review_proposals(workset: Path, decisions_path: Path, output: Path) -> dict:
    """Resolve direct review decisions into exact spans, retaining draft provenance."""
    tasks = load_tasks(workset, "development")
    decisions_bytes = decisions_path.read_bytes()
    specification = json.loads(decisions_bytes)
    source_sha256 = digest((workset / "development.jsonl").read_bytes())
    if specification["source_tasks_sha256"] != source_sha256:
        raise ValueError("Review decisions refer to a different development workset")
    decisions = specification["decisions"]
    by_id = {item["review_id"]: item for item in decisions}
    if len(by_id) != len(decisions) or set(by_id) != {task["review_id"] for task in tasks}:
        raise ValueError("Review decisions must cover each development task exactly once")
    reviewer = specification.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Review proposals require reviewer provenance")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    for task in tasks:
        decision = by_id[task["review_id"]]
        mentions = []
        for item in decision["mentions"]:
            phrase, canonical_id, sentiment = item[:3]
            occurrence = item[3] if len(item) == 4 else 0
            matches = list(re.finditer(re.escape(phrase), task["review_text"]))
            if not phrase or type(occurrence) is not int or not 0 <= occurrence < len(matches):
                raise ValueError(f"Proposed phrase occurrence does not exist for {task['review_id']}")
            match = matches[occurrence]
            mentions.append({"raw_aspect": phrase, "start_char": match.start(), "end_char": match.end(),
                             "canonical_id": canonical_id, "sentiment": sentiment})
        task["annotation"] = {
            "status": "pending", "reviewer": reviewer, "review_method": "automated",
            "reviewed_at": reviewed_at, "notes": decision.get("notes", ""),
            "flags": decision.get("flags", []),
            "mentions": sorted(mentions, key=lambda mention: (mention["start_char"], mention["end_char"])),
        }
    progress = validate_annotations(load_tasks(workset, "development"), tasks)
    # Verify that held-out input is intact without reading its review content.
    manifest = json.loads((workset / "manifest.json").read_text())
    heldout_sha256 = digest((workset / "heldout.jsonl").read_bytes())
    if heldout_sha256 != manifest["files"]["heldout.jsonl"]:
        raise ValueError("Held-out task hash differs from the original manifest")
    content = "".join(json.dumps(task, ensure_ascii=False, sort_keys=True) + "\n" for task in tasks)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(content)
    mentions = [mention for task in tasks for mention in task["annotation"]["mentions"]]
    return {
        **progress, "review_method": "automated", "reviewer": reviewer,
        "reviewed_at": reviewed_at, "proposed_mentions": len(mentions),
        "proposed_known_mentions": sum(m["canonical_id"] is not None for m in mentions),
        "proposed_unknown_mentions": sum(m["canonical_id"] is None for m in mentions),
        "reviews_without_explicit_mentions": sum(not task["annotation"]["mentions"] for task in tasks),
        "reviews_with_flags": sum(bool(task["annotation"]["flags"]) for task in tasks),
        "flag_counts": dict(sorted(Counter(flag for task in tasks for flag in task["annotation"]["flags"]).items())),
        "source_tasks_sha256": source_sha256, "decisions_sha256": digest(decisions_bytes),
        "proposals_sha256": digest(content.encode()), "heldout_sha256": heldout_sha256,
        "notice": "Automated development proposals only; not independent human labels or measured accuracy. No held-out inference performed.",
    }


def predict_development(workset: Path, output: Path) -> dict:
    from review_tag_generator import Review, ReviewAnalyzer
    from review_tag_generator.quality_queue import review_quality_queue

    if output.exists():
        raise ValueError("Prediction directory already exists; refusing overwrite")
    tasks = load_tasks(workset, "development")
    analyzer = ReviewAnalyzer(use_transformer=True, context_policy="full_review")
    analyses = []
    for index, task in enumerate(tasks, 1):
        analyses.append(analyzer.analyze(Review(task["review_id"], "vad-development", task["review_text"])))
        if index % 20 == 0:
            print(f"Analyzed development reviews: {index}/{len(tasks)}", flush=True)
    queue = review_quality_queue(analyses)
    tags = [tag for row in analyses for tag in row["tags"]]
    summary = {
        "split": "development", "reviews": len(tasks), "predicted_mentions": len(tags),
        "unknown_mentions": sum(tag["normalized_aspect_id"] is None for tag in tags),
        "queue_summary": queue["summary"], "backend": analyzer.backend, "context_policy": analyzer.context_policy,
        "source_tasks_sha256": digest((workset / "development.jsonl").read_bytes()),
        "source_tree_sha256": digest(b"".join(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes() for p in sorted((ROOT / "src/review_tag_generator").rglob("*.py")))),
        "model_weight_sha256": {name: digest((ROOT / path).read_bytes()) for name, path in {
            "aspect": "models/aspect_extractor/distilbert_weighted_lr3e5/best/model.safetensors",
            "sentiment": "models/sentiment_classifier/distilbert/best/model.safetensors",
        }.items()},
        "notice": "Unreviewed model suggestions; triage counts are not accuracy. Held-out set was not inferred.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".predictions-", dir=output.parent))
    try:
        summary["predictions_sha256"] = write_jsonl(stage / "predictions.jsonl", analyses)
        write_jsonl(stage / "quality-queue.jsonl", queue["items"])
        (stage / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return summary


def score_predictions(originals: list[dict], reviewed: list[dict], predictions: list[dict]) -> dict:
    progress = validate_annotations(originals, reviewed)
    if progress["pending"]:
        raise ValueError("All tasks need human annotation before scoring; source labels are not mention gold")
    gold = {row["review_id"]: row for row in reviewed}
    predicted = {row["review"]["review_id"]: row for row in predictions}
    if len(predicted) != len(predictions) or set(predicted) != set(gold):
        raise ValueError("Predictions must cover each reviewed task exactly once")
    counts = {name: Counter() for name in ("extraction_exact_span", "canonical_tag_exact_span_and_sentiment")}
    for review_id, row in gold.items():
        analysis = predicted[review_id]
        if analysis["review"]["review_text"] != row["review_text"]:
            raise ValueError("Predictions refer to different source text")
        mentions, tags = row["annotation"]["mentions"], analysis["tags"]
        expected_spans = {(m["start_char"], m["end_char"]) for m in mentions}
        actual_spans = {(m["start_char"], m["end_char"]) for m in tags}
        expected_tags = {(m["start_char"], m["end_char"], m["canonical_id"], m["sentiment"])
                         for m in mentions if m["canonical_id"] is not None}
        actual_tags = {(m["start_char"], m["end_char"], m["normalized_aspect_id"], m["sentiment"])
                       for m in tags if m["normalized_aspect_id"] is not None}
        for name, expected, actual in (("extraction_exact_span", expected_spans, actual_spans),
                                       ("canonical_tag_exact_span_and_sentiment", expected_tags, actual_tags)):
            counts[name].update(tp=len(actual & expected), fp=len(actual - expected), fn=len(expected - actual))
    result = {"reviews": len(reviewed), "split": "development",
              "scope": "Explicit mention-level tags; does not evaluate product aggregate judgments or implicit aspects",
              "reviewer_provenance": "Reviewer identities supplied in annotations; independent adjudication is not verified"}
    for name, count in counts.items():
        tp, fp, fn = (count[key] for key in ("tp", "fp", "fn"))
        result[name] = {"tp": tp, "fp": fp, "fn": fn,
                        "precision": tp / (tp + fp) if tp + fp else None,
                        "recall": tp / (tp + fn) if tp + fn else None,
                        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("download")
    download.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--existing-splits", type=Path, default=ROOT / "data/processed/distilbert")
    prepare_parser.add_argument("--per-split", type=int, default=100)
    predict = sub.add_parser("predict-development")
    predict.add_argument("--workset", type=Path, default=DEFAULT_OUTPUT)
    predict.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "development-predictions")
    validate = sub.add_parser("validate-annotations")
    validate.add_argument("--workset", type=Path, default=DEFAULT_OUTPUT)
    validate.add_argument("--split", choices=("development", "heldout"), required=True)
    validate.add_argument("--reviewed", type=Path, required=True)
    proposals = sub.add_parser("build-review-proposals")
    proposals.add_argument("--workset", type=Path, default=DEFAULT_OUTPUT)
    proposals.add_argument("--decisions", type=Path, required=True)
    proposals.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "development-proposed.jsonl")
    score = sub.add_parser("score-development")
    score.add_argument("--workset", type=Path, default=DEFAULT_OUTPUT)
    score.add_argument("--reviewed", type=Path, required=True)
    score.add_argument("--predictions", type=Path, default=DEFAULT_OUTPUT / "development-predictions")
    score.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "download":
        download_source(args.source)
        result = {"downloaded": str(args.source), "sha256": SOURCE_SHA256}
    elif args.command == "prepare":
        result = prepare(args.source, args.output, args.existing_splits, args.per_split)
    elif args.command == "predict-development":
        result = predict_development(args.workset, args.output)
    elif args.command == "build-review-proposals":
        result = build_review_proposals(args.workset, args.decisions, args.output)
    elif args.command == "validate-annotations":
        rows = [json.loads(line) for line in args.reviewed.read_text().splitlines() if line.strip()]
        result = validate_annotations(load_tasks(args.workset, args.split), rows)
    else:
        tasks = load_tasks(args.workset, "development")
        reviewed_bytes = args.reviewed.read_bytes()
        reviewed = [json.loads(line) for line in reviewed_bytes.decode().splitlines() if line.strip()]
        summary = json.loads((args.predictions / "summary.json").read_text())
        predictions_bytes = (args.predictions / "predictions.jsonl").read_bytes()
        if (summary["source_tasks_sha256"] != digest((args.workset / "development.jsonl").read_bytes())
                or summary["predictions_sha256"] != digest(predictions_bytes)):
            raise ValueError("Prediction provenance hashes differ from the recorded workset or predictions")
        predictions = [json.loads(line) for line in predictions_bytes.decode().splitlines() if line.strip()]
        result = score_predictions(tasks, reviewed, predictions)
        result.update(reviewed_sha256=digest(reviewed_bytes), prediction_provenance=summary)
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        with args.output_report.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
