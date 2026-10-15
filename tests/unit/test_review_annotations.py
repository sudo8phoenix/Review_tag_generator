import copy
import json

import pytest

from scripts.prepare_review_annotations import (
    audit_existing,
    build_workset,
    build_review_proposals,
    digest,
    download_source,
    load_tasks,
    score_predictions,
    text_key,
    validate_annotations,
)


def source(text, sentiment="positive", number=2):
    return {"source_row": number, "review_text": text,
            "source_review_sentiment": sentiment, "source_aspect_categories": ["Sound"]}


def pool():
    return [source(f"{label} review {index}", label, number=index + 2)
            for label in ("positive", "neutral", "negative") for index in range(10)]


def test_group_duplicates_exclude_overlap_and_conflicting_source_labels():
    rows = pool() + [source("ＧＯＯＤ sound!"), source("good  SOUND"),
                     source("old review"), source("conflict", "positive"),
                     source("conflict", "negative")]
    eligible, tasks, counts = build_workset(rows, {text_key("OLD review!"): {"train"}}, 6)
    assert counts["duplicate_rows"] == 2
    assert counts["conflicting_sentiment_groups"] == 1
    assert counts["overlapping_groups_by_existing_split"] == {"train": 1}
    assert all(r["review_text"] not in {"old review", "conflict"} for r in eligible)
    duplicate = next(r for r in eligible if text_key(r["review_text"]) == "good sound")
    assert duplicate["duplicate_group_size"] == 2
    dev = {r["review_id"] for r in tasks if r["split"] == "development"}
    heldout = {r["review_id"] for r in tasks if r["split"] == "heldout"}
    assert len(dev) == len(heldout) == 6 and dev.isdisjoint(heldout)
    assert all(r["annotation"]["status"] == "pending" and not r["annotation"]["mentions"] for r in tasks)
    assert build_workset(list(reversed(rows)), {text_key("old review"): {"train"}}, 6)[1] == tasks


def test_insufficient_stratum_fails_instead_of_silently_shrinking_sample():
    with pytest.raises(ValueError, match="Insufficient"):
        build_workset([source("only positive")], {}, 3)


def test_audit_requires_all_frozen_splits_and_records_hashes(tmp_path):
    for split in ("train", "validation", "test"):
        (tmp_path / f"{split}.jsonl").write_text(json.dumps({"review_text": "same text"}) + "\n")
    index, evidence = audit_existing(tmp_path)
    assert index["same text"] == {"train", "validation", "test"}
    assert all(item["reviews"] == 1 and len(item["sha256"]) == 64 for item in evidence.values())
    (tmp_path / "test.jsonl").unlink()
    with pytest.raises(FileNotFoundError):
        audit_existing(tmp_path)


def test_download_never_replaces_unrecognized_existing_source(tmp_path):
    path = tmp_path / "source.xlsx"
    path.write_bytes(b"user data")
    with pytest.raises(ValueError, match="refusing overwrite"):
        download_source(path)
    assert path.read_bytes() == b"user data"


def test_original_tasks_are_hash_checked(tmp_path):
    (tmp_path / "development.jsonl").write_text("{}\n")
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"development.jsonl": "wrong"}}))
    with pytest.raises(ValueError, match="Original task file has changed"):
        load_tasks(tmp_path, "development")


def annotation_task():
    return {"review_id": "r1", "review_text": "Bad screen, great wifi.", "split": "development",
            "annotation": {"status": "pending", "reviewer": None, "mentions": []}}


def approved_task():
    row = annotation_task()
    row["annotation"] = {"status": "approved", "reviewer": "human-reviewer-1", "mentions": [
        {"start_char": 4, "end_char": 10, "raw_aspect": "screen", "canonical_id": "display", "sentiment": "negative"},
        {"start_char": 18, "end_char": 22, "raw_aspect": "wifi", "canonical_id": None, "sentiment": "positive"},
    ]}
    return row


def test_pending_source_labels_do_not_count_as_gold_and_valid_unknown_is_allowed():
    original = annotation_task()
    assert validate_annotations([original], [copy.deepcopy(original)])["approved"] == 0
    assert validate_annotations([original], [approved_task()])["approved"] == 1


@pytest.mark.parametrize("defect", ["reviewer", "offset", "text", "canonical", "sentiment", "duplicate", "source", "missing_canonical"])
def test_invalid_corrections_fail(defect):
    corrected = approved_task()
    annotation = corrected["annotation"]
    mention = annotation["mentions"][0]
    if defect == "reviewer":
        annotation["reviewer"] = " "
    elif defect == "offset":
        mention["end_char"] = 999
    elif defect == "text":
        mention["raw_aspect"] = "display"
    elif defect == "canonical":
        mention["canonical_id"] = "invented"
    elif defect == "sentiment":
        mention["sentiment"] = "five stars"
    elif defect == "duplicate":
        annotation["mentions"].append(copy.deepcopy(mention))
    elif defect == "source":
        corrected["review_text"] = "Changed original text"
    elif defect == "missing_canonical":
        del mention["canonical_id"]
    with pytest.raises(ValueError):
        validate_annotations([annotation_task()], [corrected])


def test_reviewer_must_account_for_every_task_once():
    with pytest.raises(ValueError, match="exactly once"):
        validate_annotations([annotation_task()], [])


def predictions():
    return [{"review": {"review_id": "r1", "review_text": annotation_task()["review_text"]}, "tags": [
        {"start_char": 4, "end_char": 10, "normalized_aspect_id": "display", "sentiment": "positive"},
        {"start_char": 18, "end_char": 22, "normalized_aspect_id": "ports", "sentiment": "positive"},
    ]}]


def test_joint_score_penalizes_wrong_sentiment_and_false_known_mapping():
    result = score_predictions([annotation_task()], [approved_task()], predictions())
    assert result["extraction_exact_span"]["f1"] == 1
    assert result["canonical_tag_exact_span_and_sentiment"] == {
        "tp": 0, "fp": 2, "fn": 1, "precision": 0, "recall": 0, "f1": 0,
    }


def test_scoring_rejects_pending_annotations_and_mismatched_predictions():
    with pytest.raises(ValueError, match="human annotation"):
        score_predictions([annotation_task()], [annotation_task()], predictions())
    with pytest.raises(ValueError, match="exactly once"):
        score_predictions([annotation_task()], [approved_task()], [])
    changed = predictions()
    changed[0]["review"]["review_text"] = "different review"
    with pytest.raises(ValueError, match="different source text"):
        score_predictions([annotation_task()], [approved_task()], changed)


def test_automated_drafts_validate_spans_but_never_count_as_human_approval():
    draft = approved_task()
    draft["annotation"].update(status="pending", review_method="automated", reviewer="Codex")
    assert validate_annotations([annotation_task()], [draft])["approved"] == 0
    draft["annotation"]["status"] = "approved"
    with pytest.raises(ValueError, match="independent human review"):
        validate_annotations([annotation_task()], [draft])
    draft["annotation"]["status"] = "pending"
    draft["annotation"]["mentions"][0]["end_char"] = 999
    with pytest.raises(ValueError, match="offsets"):
        validate_annotations([annotation_task()], [draft])


def proposal_inputs(tmp_path):
    task = annotation_task()
    task["review_text"] = "screen then screen"
    source = json.dumps(task) + "\n"
    (tmp_path / "development.jsonl").write_text(source)
    heldout = b"held-out content must remain untouched\n"
    (tmp_path / "heldout.jsonl").write_bytes(heldout)
    manifest = {"files": {"development.jsonl": digest(source.encode()), "heldout.jsonl": digest(heldout)}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    specification = {"source_tasks_sha256": digest(source.encode()), "reviewer": "Codex", "decisions": [
        {"review_id": "r1", "mentions": [["screen", "display", "positive"], ["screen", "display", "negative", 1]]}
    ]}
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps(specification))
    return decisions, specification


def test_proposals_resolve_repeated_phrases_and_preserve_originals(tmp_path):
    decisions, _ = proposal_inputs(tmp_path)
    original = (tmp_path / "development.jsonl").read_bytes()
    summary = build_review_proposals(tmp_path, decisions, tmp_path / "proposals.jsonl")
    proposal = json.loads((tmp_path / "proposals.jsonl").read_text())
    assert summary["approved"] == 0 and summary["pending"] == 1
    assert proposal["annotation"]["review_method"] == "automated"
    assert [(m["start_char"], m["end_char"]) for m in proposal["annotation"]["mentions"]] == [(0, 6), (12, 18)]
    assert (tmp_path / "development.jsonl").read_bytes() == original
    with pytest.raises(FileExistsError):
        build_review_proposals(tmp_path, decisions, tmp_path / "proposals.jsonl")


@pytest.mark.parametrize("defect", ["source_hash", "heldout_hash", "coverage", "missing_phrase"])
def test_proposals_reject_wrong_sources_and_invalid_decisions(tmp_path, defect):
    decisions, specification = proposal_inputs(tmp_path)
    if defect == "source_hash":
        specification["source_tasks_sha256"] = "wrong"
    elif defect == "heldout_hash":
        (tmp_path / "heldout.jsonl").write_text("changed")
    elif defect == "coverage":
        specification["decisions"] = []
    else:
        specification["decisions"][0]["mentions"][0][0] = "missing"
    decisions.write_text(json.dumps(specification))
    with pytest.raises(ValueError):
        build_review_proposals(tmp_path, decisions, tmp_path / "proposals.jsonl")
    assert not (tmp_path / "proposals.jsonl").exists()
