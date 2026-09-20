"""Validated settings shared by API and worker processes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_profile: Literal["unit", "local", "release"] = "local"
    model_backend: Literal["transformer", "heuristic", "fake"] = "transformer"
    model_device: Literal["cpu", "cuda", "mps"] = "cpu"
    aspect_model_path: Path = Path("models/aspect_extractor/distilbert_weighted_lr3e5/best")
    sentiment_model_path: Path = Path("models/sentiment_classifier/distilbert/best")
    database_url: str = "postgresql+psycopg://review_tag:review_tag@127.0.0.1:5432/review_tag"
    database_statement_timeout_ms: int = Field(default=30_000, ge=1_000, le=300_000)

    max_model_tokens: int = Field(default=256, ge=32, le=512)
    extraction_stride: int = Field(default=64, ge=1)
    max_review_chars: int = Field(default=10000, ge=1, le=100000)
    max_review_tokens: int = Field(default=4096, ge=32)
    max_upload_bytes: int = Field(default=10485760, ge=1)
    max_upload_rows: int = Field(default=5000, ge=1)
    max_inline_reviews: int = Field(default=100, ge=1)
    preview_ttl_seconds: int = Field(default=1800, ge=60)
    queue_capacity: int = Field(default=100, ge=1)
    job_max_attempts: int = Field(default=3, ge=1)
    worker_lease_seconds: int = Field(default=120, ge=20)
    worker_heartbeat_seconds: int = Field(default=10, ge=1)
    inference_timeout_seconds: int = Field(default=60, ge=1)
    min_review_support: int = Field(default=3, ge=1)
    representatives_per_sentiment: int = Field(default=3, ge=1)
    default_top_k: int = Field(default=10, ge=1)
    max_top_k: int = Field(default=50, ge=1)
    page_size: int = Field(default=20, ge=1)
    max_page_size: int = Field(default=100, ge=1)
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def validate_relationships(self) -> "Settings":
        if self.extraction_stride >= self.max_model_tokens - 2:
            raise ValueError("EXTRACTION_STRIDE must be smaller than the available content tokens")
        if self.default_top_k > self.max_top_k:
            raise ValueError("DEFAULT_TOP_K must not exceed MAX_TOP_K")
        if self.page_size > self.max_page_size:
            raise ValueError("PAGE_SIZE must not exceed MAX_PAGE_SIZE")
        if self.worker_heartbeat_seconds >= self.worker_lease_seconds:
            raise ValueError("WORKER_HEARTBEAT_SECONDS must be less than WORKER_LEASE_SECONDS")
        if self.app_profile == "release" and self.model_backend != "transformer":
            raise ValueError("Release requires the trained transformer backend")
        return self

    def model_paths(self) -> tuple[Path, Path]:
        def absolute(path: Path) -> Path:
            return path if path.is_absolute() else PROJECT_ROOT / path

        return absolute(self.aspect_model_path), absolute(self.sentiment_model_path)


def get_settings() -> Settings:
    return Settings()
