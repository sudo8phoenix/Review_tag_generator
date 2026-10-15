from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from backend.app.db.models import (
    AnalysisPreview,
    AnalysisRun,
    AspectMention,
    ApplicationSetting,
    IdempotencyRequest,
    JobItem,
    ProcessingJob,
    Product,
    ProductSnapshot,
    ReviewRecord,
    utcnow,
)
from backend.app.repository import Conflict, Repository, text_hash


def saved_product(repository, name, version):
    with repository.transaction() as db:
        product = Product(id=uuid4(), source='manual', name=name, category='electronics')
        db.add(product)
        db.flush()
        review_id = uuid4()
        text = f'{name} has a bright screen.'
        review = ReviewRecord(id=review_id, product_id=product.id, source='manual', review_text=text,
            text_sha256=sha256(text.encode()).hexdigest(), dedup_key=text_hash(text), analysis_status='completed')
        db.add(review)
        db.flush()
        payload = {'review': {'review_id': str(review_id), 'product_id': str(product.id), 'review_text': text},
            'tags': [{'normalized_aspect': 'display', 'sentiment': 'positive', 'tag': 'bright display',
                'confidence': 0.9, 'raw_aspect': 'screen', 'start_char': 16, 'end_char': 22,
                'normalized_aspect_id': 'display', 'normalization_method': 'ontology',
                'normalization_similarity': 1.0, 'aspect_confidence': 0.9,
                'sentiment_confidence': 0.9, 'probabilities': {'positive': 0.9, 'neutral': 0.05, 'negative': 0.05},
                'context_start_char': 0, 'context_end_char': len(text)}]}
        run_id = uuid4()
        db.add(AnalysisRun(id=run_id, review_id=review_id, pipeline_version=version, payload=payload,
            original_text_sha256=review.text_sha256, backend='test', context_policy='full_review', elapsed_ms=1))
        db.add(AspectMention(analysis_run_id=run_id, raw_aspect='screen', start_char=16, end_char=22,
            canonical_id='display', canonical_label='display', aspect_confidence=0.9, sentiment='positive',
            sentiment_confidence=0.9, summary_confidence=0.9,
            probabilities={'positive': 0.9, 'neutral': 0.05, 'negative': 0.05},
            normalization_method='ontology', normalization_similarity=1.0, tag='bright display',
            context_start_char=0, context_end_char=len(text)))
        repository.snapshot(db, product, version)
        return str(product.id), text


@pytest.fixture
def repository(tmp_path):
    return Repository(f"sqlite:///{tmp_path / 'saved-data.sqlite3'}")


def test_clear_removes_only_selected_product_and_all_saved_evidence(repository):
    version = 'pipeline-v1'
    target_id, target_text = saved_product(repository, 'Target', version)
    other_id, _ = saved_product(repository, 'Other', version)
    with repository.transaction() as db:
        job = ProcessingJob(id=uuid4(), product_id=UUID(target_id), type='import', status='completed', stage='finished',
            pipeline_version=version, total_rows=1, accepted_rows=1, rejected_rows=0, duplicate_rows=0)
        db.add(job)
        db.flush()
        db.add(JobItem(job_id=job.id, item_key='1', status='completed'))
        db.add(IdempotencyRequest(endpoint_scope=f'product:{target_id}', key='old-key',
            request_sha256='a' * 64, response={'job_id': str(job.id)}, job_id=job.id))
        db.add(AnalysisPreview(id=uuid4(), product_id=UUID(target_id), review_text='temporary',
            text_sha256=sha256(b'temporary').hexdigest(), status='completed', pipeline_version=version,
            expires_at=utcnow() + timedelta(hours=1)))

    result = repository.remove_product_data(target_id, 'pipeline-v2')
    assert result == {'product_id': target_id, 'reviews_removed': 1, 'deleted': False, 'cleared': True}
    with repository.transaction() as db:
        target = db.get(Product, UUID(target_id))
        assert target.data_revision == 1
        assert target.current_snapshot_id is not None
        empty = db.get(ProductSnapshot, target.current_snapshot_id)
        assert empty.pipeline_version == 'pipeline-v2'
        assert empty.payload['review_count'] == 0
        assert db.scalar(select(func.count()).select_from(ReviewRecord).where(ReviewRecord.product_id == UUID(target_id))) == 0
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 1
        assert db.scalar(select(func.count()).select_from(AspectMention)) == 1
        assert db.scalar(select(func.count()).select_from(AnalysisPreview).where(AnalysisPreview.product_id == UUID(target_id))) == 0
        assert db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.product_id == UUID(target_id))) == 0
        assert db.scalar(select(func.count()).select_from(IdempotencyRequest).where(IdempotencyRequest.endpoint_scope == f'product:{target_id}')) == 0
        assert db.scalar(select(func.count()).select_from(ProductSnapshot).where(ProductSnapshot.product_id == UUID(other_id))) == 1
        assert db.scalar(select(func.count()).select_from(ReviewRecord).where(ReviewRecord.product_id == UUID(other_id))) == 1

    job_id = repository.enqueue(target_id, [(1, target_text)], 'pipeline-v2')
    assert repository.job(job_id)['accepted_rows'] == 1


@pytest.mark.parametrize('active_kind', ['job', 'preview'])
def test_active_work_rejects_removal_without_partial_deletion(repository, active_kind):
    version = 'pipeline-v1'
    product_id, _ = saved_product(repository, 'Busy product', version)
    with repository.transaction() as db:
        if active_kind == 'job':
            db.add(ProcessingJob(id=uuid4(), product_id=UUID(product_id), type='import', status='queued', stage='queued',
                pipeline_version=version, total_rows=0, accepted_rows=0, rejected_rows=0, duplicate_rows=0))
        else:
            db.add(AnalysisPreview(id=uuid4(), product_id=UUID(product_id), review_text='temporary',
                text_sha256=sha256(b'temporary').hexdigest(), status='queued', pipeline_version=version,
                expires_at=utcnow() + timedelta(hours=1)))

    with pytest.raises(Conflict, match='active jobs or previews'):
        repository.remove_product_data(product_id, version)
    with repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewRecord).where(ReviewRecord.product_id == UUID(product_id))) == 1
        assert db.scalar(select(func.count()).select_from(ProductSnapshot).where(ProductSnapshot.product_id == UUID(product_id))) == 1


def test_delete_product_and_missing_product(repository):
    product_id, _ = saved_product(repository, 'Delete me', 'pipeline-v1')
    result = repository.remove_product_data(product_id, 'pipeline-v1', delete_product=True)
    assert result == {'product_id': product_id, 'reviews_removed': 1, 'deleted': True, 'cleared': False}
    with pytest.raises(LookupError, match='Product not found'):
        repository.remove_product_data(product_id, 'pipeline-v1')


def test_remove_import_preserves_other_batches_and_detaches_regeneration_items(repository):
    version = 'pipeline-v1'
    product_id, first_text = saved_product(repository, 'Imported product', version)
    second_review_id = uuid4()
    second_text = 'Other batch review stays saved.'
    with repository.transaction() as db:
        product = db.get(Product, UUID(product_id))
        second_review = ReviewRecord(id=second_review_id, product_id=product.id, source='manual',
            review_text=second_text, text_sha256=sha256(second_text.encode()).hexdigest(),
            dedup_key=text_hash(second_text), analysis_status='pending')
        db.add(second_review)
        duplicate_only = ProcessingJob(id=uuid4(), product_id=product.id, type='import', status='completed', stage='finished',
            pipeline_version=version, total_rows=1, accepted_rows=0, rejected_rows=0, duplicate_rows=1,
            input_filename='duplicates.csv')
        first_batch = ProcessingJob(id=uuid4(), product_id=product.id, type='import', status='completed', stage='finished',
            pipeline_version=version, total_rows=1, accepted_rows=1, rejected_rows=0, duplicate_rows=0,
            input_filename='first.csv')
        regeneration = ProcessingJob(id=uuid4(), product_id=product.id, type='regeneration', status='completed', stage='finished',
            pipeline_version=version, total_rows=1, accepted_rows=1, rejected_rows=0, duplicate_rows=0,
            parent_job_id=first_batch.id)
        db.add_all([duplicate_only, first_batch, regeneration])
        db.flush()
        first_review_id = db.scalar(select(ReviewRecord.id).where(ReviewRecord.product_id == product.id,
            ReviewRecord.id != second_review_id))
        # A retry/regeneration row can retain a review reference independently
        # of the import row that originally inserted it.
        db.add(JobItem(job_id=first_batch.id, item_key='imported-review', review_id=first_review_id, status='completed'))
        db.add(JobItem(job_id=regeneration.id, item_key='regenerated-review', review_id=first_review_id, status='completed'))
        db.add(IdempotencyRequest(endpoint_scope=f'product:{product_id}', key='batch-key',
            request_sha256='b' * 64, response={'job_id': str(first_batch.id)}, job_id=first_batch.id))

    rows = repository.saved_imports(product_id)
    assert {row['filename'] for row in rows} == {'first.csv', 'duplicates.csv'}
    removed = repository.remove_import(product_id, str(first_batch.id), version)
    assert removed == {'product_id': product_id, 'import_id': str(first_batch.id), 'reviews_removed': 1}
    with repository.transaction() as db:
        assert db.get(ReviewRecord, first_review_id) is None
        assert db.get(ReviewRecord, second_review_id) is not None
        assert db.scalar(select(func.count()).select_from(AnalysisRun).join(ReviewRecord).where(
            ReviewRecord.product_id == UUID(product_id))) == 0
        assert db.scalar(select(func.count()).select_from(ProductSnapshot).where(
            ProductSnapshot.product_id == UUID(product_id))) == 1
        detached = db.get(JobItem, (regeneration.id, 'regenerated-review'))
        assert detached.review_id is None and detached.status == 'removed'
        assert db.get(ProcessingJob, regeneration.id).parent_job_id is None
        assert db.get(ProcessingJob, duplicate_only.id) is not None
        assert db.scalar(select(func.count()).select_from(IdempotencyRequest).where(
            IdempotencyRequest.job_id == first_batch.id)) == 0
        assert db.get(Product, UUID(product_id)).current_snapshot_id is not None
    assert repository.remove_import(product_id, str(duplicate_only.id), version)['reviews_removed'] == 0
    with repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewRecord).where(
            ReviewRecord.product_id == UUID(product_id))) == 1


def test_demo_product_removal_does_not_reseed_on_initialize(repository):
    repository.initialize()
    result = repository.remove_product_data('demo-laptop', 'pipeline-v1', delete_product=True)
    assert result['deleted'] is True
    repository.initialize()
    with repository.transaction() as db:
        assert db.get(Product, UUID('00000000-0000-4000-8000-000000000001')) is None
        assert db.get(ApplicationSetting, 'demo_seeded').value == 'true'
