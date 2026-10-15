"""PostgreSQL repository/worker integration coverage.

Set POSTGRES_TEST_URL to a disposable database whose name contains ``test``.
The test upgrades that database to Alembic head and only deletes its own rows.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, update

from backend.app.db.models import (
    AnalysisPreview,
    IdempotencyRequest,
    JobItem,
    ProcessingJob,
    Product,
    ProductSnapshot,
    ReviewRecord,
)
from backend.app.repository import Conflict, Repository
from backend.app.corrections import CorrectionInput, Corrections, MentionReference
from backend.app.annotations import AnnotationInput, Annotations, ReviewReference
from backend.app.worker import Worker
from review_tag_generator import ReviewAnalyzer


ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "backend" / "alembic.ini"


def _test_database_url() -> str:
    url = os.environ.get("POSTGRES_TEST_URL", "")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not set; PostgreSQL repository test was not run")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("POSTGRES_TEST_URL must use postgresql+psycopg, never SQLite")
    database = url.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if "test" not in database:
        pytest.fail("refusing to write to a database whose name does not contain 'test'")
    return url


def _alembic_config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _cleanup(repository: Repository, product_id: UUID) -> None:
    """Delete only records owned by the test product, in foreign-key order."""
    with repository.transaction() as db:
        job_ids = select(ProcessingJob.id).where(ProcessingJob.product_id == product_id)
        db.execute(update(Product).where(Product.id == product_id).values(current_snapshot_id=None))
        db.execute(delete(IdempotencyRequest).where(IdempotencyRequest.job_id.in_(job_ids)))
        db.execute(delete(JobItem).where(JobItem.job_id.in_(job_ids)))
        db.execute(delete(ProcessingJob).where(ProcessingJob.product_id == product_id))
        db.execute(delete(AnalysisPreview).where(AnalysisPreview.product_id == product_id))
        db.execute(delete(ProductSnapshot).where(ProductSnapshot.product_id == product_id))
        db.execute(delete(ReviewRecord).where(ReviewRecord.product_id == product_id))
        db.execute(delete(Product).where(Product.id == product_id))


@pytest.mark.integration
def test_postgres_enqueue_dedupe_skip_locked_and_worker_snapshot() -> None:
    url = _test_database_url()
    command.upgrade(_alembic_config(url), "head")
    repository = Repository(url)
    product_id: UUID | None = None
    try:
        product = repository.create_product("PostgreSQL integration test")
        product_id = UUID(product["id"])
        analyzer = ReviewAnalyzer(use_transformer=False, context_policy="full_review")
        worker = Worker(repository, analyzer)

        first_text = "The battery lasts all day."
        first_job = repository.enqueue(
            str(product_id), [(1, first_text)], worker.version, "integration-key"
        )
        assert repository.enqueue(
            str(product_id), [(1, first_text)], worker.version, "integration-key"
        ) == first_job
        with pytest.raises(Conflict, match="different content"):
            repository.enqueue(
                str(product_id), [(1, "The battery drains quickly.")], worker.version, "integration-key"
            )

        duplicate_job = repository.enqueue(
            str(product_id), [(1, first_text)], worker.version
        )
        duplicate = repository.job(duplicate_job)
        assert duplicate["status"] == "completed"
        assert duplicate["duplicate_rows"] == 1
        assert duplicate["accepted_rows"] == 0

        second_job = repository.enqueue(
            str(product_id), [(1, "The screen is bright and clear.")], worker.version
        )

        # Hold the first queued row lock on one connection. A separate worker
        # claim must skip it and lease the second eligible job.
        with repository.engine.connect() as connection:
            lock_transaction = connection.begin()
            connection.execute(
                select(ProcessingJob.id)
                .where(ProcessingJob.id == UUID(first_job))
                .with_for_update()
            )
            try:
                second_worker = Worker(repository, analyzer)
                assert repository.claim(second_worker.id, worker.version) == second_job
            finally:
                lock_transaction.rollback()

        second_worker.process_job(second_job)
        assert repository.job(second_job)["status"] == "completed"

        assert repository.claim(worker.id, worker.version) == first_job
        worker.process_job(first_job)
        assert repository.job(first_job)["status"] == "completed"

        detail = repository.detail(str(product_id), worker.version, analyzer.backend)
        assert detail["snapshot_id"]
        assert detail["stale"] is False
        assert detail["review_counts"]["completed"] == 2
        assert detail["insights"]["review_count"] == 2
        assert len(detail["reviews"]) == 2
        review = detail['reviews'][0]
        tag = review['tags'][0]
        reference = {'snapshot_id': detail['snapshot_id'], 'review_id': review['review']['review_id'],
                     'start_char': tag['start_char'], 'end_char': tag['end_char']}
        service = Corrections(repository)
        decision = CorrectionInput(**reference, request_id=uuid4(), decision='edited', reviewer='PostgreSQL test reviewer',
            reason='Exercise durable reviewer decision JSON and UUID columns.',
            canonical_id=tag['normalized_aspect_id'], sentiment='neutral')
        recorded = service.save(str(product_id), decision)
        assert service.save(str(product_id), decision)['id'] == recorded['id']
        assert service.history(str(product_id), MentionReference(**reference))['latest_id'] == recorded['id']
        assert service.export(str(product_id))['items'][0]['resolution']['sentiment'] == 'neutral'
        annotations = Annotations(repository)
        annotation_reference = ReviewReference(snapshot_id=reference['snapshot_id'], review_id=reference['review_id'])
        draft = annotations.detail(str(product_id), annotation_reference)
        annotation_request = AnnotationInput(**annotation_reference.model_dump(), request_id=uuid4(),
            expected_correction_id=draft['correction_revision'], status='reviewed', reviewer='PostgreSQL test reviewer',
            reason='Verify full-review annotation persistence.', mentions=draft['mentions'])
        annotated = annotations.save(str(product_id), annotation_request)
        assert annotations.save(str(product_id), annotation_request)['id'] == annotated['id']
        assert annotations.worklist(str(product_id))['summary']['reviewed'] == 1
        assert annotations.export(str(product_id), UUID(detail['snapshot_id']))['items'][0]['id'] == annotated['id']
        assert repository.detail(str(product_id), worker.version, analyzer.backend) == detail
    finally:
        if product_id is not None:
            _cleanup(repository, product_id)
        repository.engine.dispose()
