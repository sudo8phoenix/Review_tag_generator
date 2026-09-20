"""Create the durable PostgreSQL schema for v1 review processing.

Revision ID: 0001_initial_postgres_schema
Revises:
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_postgres_schema"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("external_product_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("data_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_products_source_external",
        "products",
        ["source", "external_product_id"],
        unique=True,
        postgresql_where=sa.text("external_product_id IS NOT NULL"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("external_review_id", sa.String(length=255), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("dedup_key", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("helpful_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.UniqueConstraint("product_id", "dedup_key", name="uq_reviews_product_dedup"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        sa.CheckConstraint("helpful_votes >= 0", name="ck_reviews_helpful_votes"),
        sa.CheckConstraint("char_length(review_text) BETWEEN 1 AND 10000", name="ck_reviews_text_length"),
    )
    op.create_index("ix_reviews_product_submitted_id", "reviews", ["product_id", "submitted_at", "id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("review_id", UUID, sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("original_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("backend", sa.String(length=30), nullable=False),
        sa.Column("context_policy", sa.String(length=30), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "pipeline_version", name="uq_analysis_review_pipeline"),
    )

    op.create_table(
        "aspect_mentions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("analysis_run_id", UUID, sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_aspect", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("canonical_id", sa.String(length=100), nullable=True),
        sa.Column("canonical_label", sa.String(length=100), nullable=True),
        sa.Column("aspect_confidence", sa.Numeric(10, 8), nullable=False),
        sa.Column("sentiment", sa.String(length=8), nullable=False),
        sa.Column("sentiment_confidence", sa.Numeric(10, 8), nullable=False),
        sa.Column("summary_confidence", sa.Numeric(10, 8), nullable=False),
        sa.Column("probabilities", JSONB, nullable=False),
        sa.Column("normalization_method", sa.String(length=20), nullable=False),
        sa.Column("normalization_similarity", sa.Numeric(10, 8), nullable=True),
        sa.Column("tag", sa.String(length=200), nullable=True),
        sa.Column("context_start_char", sa.Integer(), nullable=False),
        sa.Column("context_end_char", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", "start_char", "end_char", name="uq_mentions_run_span"),
        sa.CheckConstraint("start_char >= 0 AND end_char > start_char", name="ck_mentions_offsets"),
        sa.CheckConstraint("context_start_char >= 0 AND context_end_char > context_start_char", name="ck_mentions_context_offsets"),
        sa.CheckConstraint("aspect_confidence BETWEEN 0 AND 1", name="ck_mentions_aspect_confidence"),
        sa.CheckConstraint("sentiment_confidence BETWEEN 0 AND 1", name="ck_mentions_sentiment_confidence"),
        sa.CheckConstraint("summary_confidence BETWEEN 0 AND 1", name="ck_mentions_summary_confidence"),
        sa.CheckConstraint("normalization_similarity IS NULL OR normalization_similarity BETWEEN 0 AND 1", name="ck_mentions_similarity"),
        sa.CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name="ck_mentions_sentiment"),
    )
    op.create_index("ix_mentions_canonical", "aspect_mentions", ["canonical_id"])
    op.create_index("ix_mentions_run", "aspect_mentions", ["analysis_run_id"])

    op.create_table(
        "product_snapshots",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("aggregate_version", sa.String(length=64), nullable=False),
        sa.Column("data_revision", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "aggregate_version", "data_revision", name="uq_snapshot_product_version_revision"),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_job_id", UUID, sa.ForeignKey("processing_jobs.id"), nullable=True),
        sa.Column("leased_by", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "total_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0 AND duplicate_rows >= 0 AND completed_rows >= 0 AND failed_rows >= 0",
            name="ck_jobs_nonnegative_counts",
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_jobs_attempt"),
    )
    op.create_index("ix_jobs_claim", "processing_jobs", ["status", "lease_expires_at", "created_at"])

    op.create_table(
        "job_items",
        sa.Column("job_id", UUID, sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("item_key", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("review_id", UUID, sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.CheckConstraint("attempt >= 0", name="ck_job_items_attempt"),
    )

    op.create_table(
        "idempotency_requests",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("endpoint_scope", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("response", JSONB, nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("processing_jobs.id"), nullable=True),
        sa.UniqueConstraint("endpoint_scope", "key", name="uq_idempotency_scope_key"),
    )

    op.create_table(
        "analysis_previews",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("analysis", JSONB, nullable=True),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("leased_by", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_previews_status_expiry", "analysis_previews", ["status", "expires_at"])

    op.create_table(
        "worker_status",
        sa.Column("worker_id", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("heartbeat", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("model_health", sa.String(length=30), nullable=False),
        sa.Column("busy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column("products", sa.Column("current_snapshot_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_products_current_snapshot", "products", "product_snapshots", ["current_snapshot_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_current_snapshot", "products", type_="foreignkey")
    op.drop_column("products", "current_snapshot_id")
    op.drop_table("worker_status")
    op.drop_index("ix_previews_status_expiry", table_name="analysis_previews")
    op.drop_table("analysis_previews")
    op.drop_table("idempotency_requests")
    op.drop_table("job_items")
    op.drop_index("ix_jobs_claim", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_table("product_snapshots")
    op.drop_index("ix_mentions_run", table_name="aspect_mentions")
    op.drop_index("ix_mentions_canonical", table_name="aspect_mentions")
    op.drop_table("aspect_mentions")
    op.drop_table("analysis_runs")
    op.drop_index("ix_reviews_product_submitted_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("uq_products_source_external", table_name="products")
    op.drop_table("products")
