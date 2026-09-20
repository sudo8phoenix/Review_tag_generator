"""PostgreSQL persistence schema for reviews, immutable analyses, and snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String,
    Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("uq_products_source_external", "source", "external_product_id", unique=True,
              postgresql_where=text("external_product_id IS NOT NULL")),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(200))
    data_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product_snapshots.id", name="fk_products_current_snapshot", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviews: Mapped[list["ReviewRecord"]] = relationship(back_populates="product", foreign_keys="ReviewRecord.product_id")


class ReviewRecord(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "dedup_key", name="uq_reviews_product_dedup"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        CheckConstraint("helpful_votes >= 0", name="ck_reviews_helpful_votes"),
        CheckConstraint("char_length(review_text) BETWEEN 1 AND 10000", name="ck_reviews_text_length"),
        Index("ix_reviews_product_submitted_id", "product_id", "submitted_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_review_id: Mapped[str | None] = mapped_column(String(255))
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    helpful_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    product: Mapped[Product] = relationship(back_populates="reviews", foreign_keys=[product_id])
    analyses: Mapped[list["AnalysisRun"]] = relationship(back_populates="review", cascade="all, delete-orphan")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("review_id", "pipeline_version", name="uq_analysis_review_pipeline"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    original_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    backend: Mapped[str] = mapped_column(String(30), nullable=False)
    context_policy: Mapped[str] = mapped_column(String(30), nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    review: Mapped[ReviewRecord] = relationship(back_populates="analyses")
    mentions: Mapped[list["AspectMention"]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")


class AspectMention(Base):
    __tablename__ = "aspect_mentions"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "start_char", "end_char", name="uq_mentions_run_span"),
        CheckConstraint("start_char >= 0 AND end_char > start_char", name="ck_mentions_offsets"),
        CheckConstraint("context_start_char >= 0 AND context_end_char > context_start_char", name="ck_mentions_context_offsets"),
        CheckConstraint("aspect_confidence BETWEEN 0 AND 1", name="ck_mentions_aspect_confidence"),
        CheckConstraint("sentiment_confidence BETWEEN 0 AND 1", name="ck_mentions_sentiment_confidence"),
        CheckConstraint("summary_confidence BETWEEN 0 AND 1", name="ck_mentions_summary_confidence"),
        CheckConstraint("normalization_similarity IS NULL OR normalization_similarity BETWEEN 0 AND 1", name="ck_mentions_similarity"),
        CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name="ck_mentions_sentiment"),
        Index("ix_mentions_canonical", "canonical_id"),
        Index("ix_mentions_run", "analysis_run_id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    raw_aspect: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_id: Mapped[str | None] = mapped_column(String(100))
    canonical_label: Mapped[str | None] = mapped_column(String(100))
    aspect_confidence: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(8), nullable=False)
    sentiment_confidence: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    summary_confidence: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalization_method: Mapped[str] = mapped_column(String(20), nullable=False)
    normalization_similarity: Mapped[float | None] = mapped_column(Numeric(10, 8))
    tag: Mapped[str | None] = mapped_column(String(200))
    context_start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    context_end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="mentions")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (
        UniqueConstraint("product_id", "aggregate_version", "data_revision", name="uq_snapshot_product_version_revision"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("total_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0 AND duplicate_rows >= 0 AND completed_rows >= 0 AND failed_rows >= 0", name="ck_jobs_nonnegative_counts"),
        CheckConstraint("attempt >= 0", name="ck_jobs_attempt"),
        Index("ix_jobs_claim", "status", "lease_expires_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    accepted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    parent_job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("processing_jobs.id"))
    leased_by: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class JobItem(Base):
    __tablename__ = "job_items"
    __table_args__ = (CheckConstraint("attempt >= 0", name="ck_job_items_attempt"),)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"), primary_key=True)
    item_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    review_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("reviews.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_summary: Mapped[str | None] = mapped_column(String(500))


class IdempotencyRequest(Base):
    __tablename__ = "idempotency_requests"
    __table_args__ = (UniqueConstraint("endpoint_scope", "key", name="uq_idempotency_scope_key"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    endpoint_scope: Mapped[str] = mapped_column(String(200), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("processing_jobs.id"))


class AnalysisPreview(Base):
    __tablename__ = "analysis_previews"
    __table_args__ = (Index("ix_previews_status_expiry", "status", "expires_at"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    analysis: Mapped[dict | None] = mapped_column(JSONB)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    leased_by: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkerStatus(Base):
    __tablename__ = "worker_status"
    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_health: Mapped[str] = mapped_column(String(30), nullable=False)
    busy: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
