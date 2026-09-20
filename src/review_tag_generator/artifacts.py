"""Verification of the exact model directories selected by the Kaggle run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class CheckpointVerificationError(RuntimeError):
    pass


REQUIRED_FILES = {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"}
LABEL_MAPS = {
    "aspect": {0: "O", 1: "B-ASP", 2: "I-ASP"},
    "sentiment": {0: "negative", 1: "neutral", 2: "positive"},
}


def directory_sha256(path: Path) -> str:
    """Match the notebook hash: relative filenames followed by file contents."""
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        with file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def verify_checkpoint(path: str | Path, manifest_path: str | Path, task: str) -> str:
    checkpoint = Path(path)
    manifest_file = Path(manifest_path)
    if not checkpoint.is_dir():
        raise CheckpointVerificationError(f"{task} checkpoint directory is missing: {checkpoint}")
    absent = sorted(name for name in REQUIRED_FILES if not (checkpoint / name).is_file())
    if absent:
        raise CheckpointVerificationError(f"{task} checkpoint is incomplete: {', '.join(absent)}")
    if not manifest_file.is_file():
        raise CheckpointVerificationError(f"{task} manifest is missing: {manifest_file}")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        expected = manifest["checkpoint"]["sha256"]
        config = json.loads((checkpoint / "config.json").read_text(encoding="utf-8"))
        label_map = {int(index): label for index, label in config["id2label"].items()}
    except (KeyError, ValueError, TypeError, OSError) as exc:
        raise CheckpointVerificationError(f"{task} manifest/config is invalid") from exc
    if manifest.get("mode") != "transformer" or not isinstance(expected, str) or len(expected) != 64:
        raise CheckpointVerificationError(f"{task} manifest is not a verified transformer run")
    if config.get("model_type") != "distilbert" or label_map != LABEL_MAPS[task]:
        raise CheckpointVerificationError(f"{task} checkpoint has the wrong model or label map")
    actual = directory_sha256(checkpoint)
    if actual != expected:
        raise CheckpointVerificationError(f"{task} checkpoint hash mismatch: expected {expected}, got {actual}")
    return actual
