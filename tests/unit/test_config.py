from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.config import PROJECT_ROOT, Settings


def test_default_paths_are_project_relative():
    aspect, sentiment = Settings(_env_file=None).model_paths()
    assert aspect == PROJECT_ROOT / "models/aspect_extractor/distilbert_weighted_lr3e5/best"
    assert sentiment == PROJECT_ROOT / "models/sentiment_classifier/distilbert/best"


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("MAX_REVIEW_CHARS", "1234")
    monkeypatch.setenv("MODEL_BACKEND", "fake")
    settings = Settings(_env_file=None)
    assert settings.max_review_chars == 1234
    assert settings.model_backend == "fake"


@pytest.mark.parametrize("values", [
    {"extraction_stride": 255},
    {"default_top_k": 51},
    {"page_size": 101},
    {"worker_heartbeat_seconds": 120},
    {"app_profile": "release", "model_backend": "heuristic"},
])
def test_invalid_settings_fail(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
