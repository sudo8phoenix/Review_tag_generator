"""PostgreSQL-only migration verification.

Set POSTGRES_TEST_URL to a disposable database whose name contains ``test`` to
run this suite. SQLite is deliberately not accepted: JSONB, UUID, partial
indexes, and checks are part of the production contract.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "backend" / "alembic.ini"
REQUIRED_TABLES = {
    "products",
    "reviews",
    "analysis_runs",
    "aspect_mentions",
    "product_snapshots",
    "processing_jobs",
    "job_items",
    "idempotency_requests",
    "analysis_previews",
    "worker_status",
}


def _test_database_url() -> str:
    url = os.environ.get("POSTGRES_TEST_URL", "")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not set; PostgreSQL migration suite was not run")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("POSTGRES_TEST_URL must use postgresql+psycopg, never SQLite")
    database = url.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "test" not in database:
        pytest.fail("refusing destructive migration test outside a database whose name contains 'test'")
    return url


def _config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.mark.integration
def test_migration_upgrade_downgrade_upgrade_and_constraints() -> None:
    url = _test_database_url()
    config = _config(url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        assert REQUIRED_TABLES <= set(inspector.get_table_names())
        assert "current_snapshot_id" in {column["name"] for column in inspector.get_columns("products")}
        assert "uq_reviews_product_dedup" in {item["name"] for item in inspector.get_unique_constraints("reviews")}
        assert "ix_jobs_claim" in {item["name"] for item in inspector.get_indexes("processing_jobs")}
        checks = {item["name"] for item in inspector.get_check_constraints("reviews")}
        assert {"ck_reviews_rating", "ck_reviews_helpful_votes", "ck_reviews_text_length"} <= checks
        mention_checks = {item["name"] for item in inspector.get_check_constraints("aspect_mentions")}
        assert {"ck_mentions_offsets", "ck_mentions_sentiment", "ck_mentions_similarity"} <= mention_checks

        # Exercise actual PostgreSQL enforcement, not just constraint names.
        # Each failed insert runs in its own transaction so the connection
        # remains usable after PostgreSQL marks a transaction as aborted.
        product_id = uuid4()
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO products (id, source, name, category, data_revision, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now())",
                (product_id, "integration-test", "Migration test product", "test", 0),
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO reviews (id, product_id, source, review_text, text_sha256, dedup_key, "
                    "rating, helpful_votes, submitted_at, analysis_status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 0, now(), %s)",
                    (uuid4(), product_id, "integration-test", "Invalid rating", "a" * 64, "bad-rating", 6, "pending"),
                )

        valid_review_id = uuid4()
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO reviews (id, product_id, source, review_text, text_sha256, dedup_key, "
                "rating, helpful_votes, submitted_at, analysis_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 5, 0, now(), %s)",
                (valid_review_id, product_id, "integration-test", "Valid review", "b" * 64, "same-key", "pending"),
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO reviews (id, product_id, source, review_text, text_sha256, dedup_key, "
                    "rating, helpful_votes, submitted_at, analysis_status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 5, 0, now(), %s)",
                    (uuid4(), product_id, "integration-test", "Duplicate review", "c" * 64, "same-key", "pending"),
                )
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    command.upgrade(config, "head")
