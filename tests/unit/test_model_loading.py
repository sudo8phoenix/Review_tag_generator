import json

import pytest

from review_tag_generator import ReviewAnalyzer
from review_tag_generator.artifacts import CheckpointVerificationError, verify_checkpoint


def test_explicit_heuristic_never_loads_model():
    analyzer = ReviewAnalyzer(use_transformer=False, aspect_model_path="/missing", sentiment_model_path="/missing")
    assert analyzer.backend == "heuristic"


@pytest.mark.parametrize("mode", [True, "auto"])
def test_transformer_missing_assets_fail_closed(mode, tmp_path):
    with pytest.raises(CheckpointVerificationError, match="missing"):
        ReviewAnalyzer(use_transformer=mode, aspect_model_path=str(tmp_path / "missing"))


def test_wrong_label_map_rejected_before_hashing(tmp_path):
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    for name in ("tokenizer.json", "tokenizer_config.json", "model.safetensors"):
        (checkpoint / name).write_bytes(b"fixture")
    (checkpoint / "config.json").write_text(json.dumps({"model_type": "distilbert", "id2label": {"0": "positive"}}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"mode": "transformer", "checkpoint": {"sha256": "0" * 64}}))
    with pytest.raises(CheckpointVerificationError, match="wrong model or label map"):
        verify_checkpoint(checkpoint, manifest, "aspect")


def test_tampered_checkpoint_fails_hash_verification(tmp_path):
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    for name in ("tokenizer.json", "tokenizer_config.json", "model.safetensors"):
        (checkpoint / name).write_bytes(b"fixture")
    (checkpoint / "config.json").write_text(json.dumps({
        "model_type": "distilbert",
        "id2label": {"0": "O", "1": "B-ASP", "2": "I-ASP"},
    }))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"mode": "transformer", "checkpoint": {"sha256": "0" * 64}}))
    with pytest.raises(CheckpointVerificationError, match="hash mismatch"):
        verify_checkpoint(checkpoint, manifest, "aspect")
