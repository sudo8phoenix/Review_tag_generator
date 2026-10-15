"""Transactional storage shared by the HTTP API and durable workers."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event, func, select, or_
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import (Base, Product, ReviewRecord, AnalysisRun, AspectMention,
    ProductSnapshot, ProcessingJob, JobItem, IdempotencyRequest, AnalysisPreview, WorkerStatus, utcnow)
from review_tag_generator import Review
from review_tag_generator.aggregation import SavedReviewAnalysis, aggregate_saved_analyses
from review_tag_generator.schemas import Sentiment, TagResult

ROOT = Path(__file__).resolve().parents[2]
DEMO_ID = UUID('00000000-0000-4000-8000-000000000001')
AGGREGATE_VERSION = sha256((ROOT / 'src/review_tag_generator/aggregation.py').read_bytes()).hexdigest()


def pipeline_version(backend):
    digest = sha256(backend.encode())
    digest.update(json.dumps({name: os.environ.get(name) for name in
        ['SEMANTIC_MODEL_PATH', 'SEMANTIC_MODEL_REVISION', 'NORMALIZATION_THRESHOLD', 'MODEL_DEVICE']}, sort_keys=True).encode())
    for path in sorted((ROOT / 'src/review_tag_generator').rglob('*.py')):
        digest.update(path.read_bytes())
    for path in sorted((ROOT / 'src/review_tag_generator/data').glob('*.json')):
        digest.update(path.read_bytes())
    for name in ['A2/aspect_training_manifest.json', 'A3/sentiment_training_manifest.json', 'current/policy.json']:
        digest.update((ROOT / 'audit/evidence' / name).read_bytes())
    return digest.hexdigest()


def product_uuid(value):
    try:
        return DEMO_ID if value == 'demo-laptop' else UUID(str(value))
    except ValueError as exc:
        raise LookupError('Product not found') from exc


def text_hash(value):
    # Preserve the exact review for inference; normalize only the duplicate key.
    return sha256(' '.join(value.split()).casefold().encode()).hexdigest()


class Conflict(ValueError):
    pass


class QueueFull(ValueError):
    pass


class Repository:
    def __init__(self, url=None):
        url = url or os.environ.get('DATABASE_URL')
        if not url:
            path = Path(os.environ.get('DEMO_DATABASE', ROOT / '.demo/application.sqlite3'))
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f'sqlite:///{path}'
        self.engine = create_engine(url, pool_pre_ping=True)
        self.storage = 'PostgreSQL' if self.engine.dialect.name == 'postgresql' else 'local SQLite'
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def setup(connection, _):
                connection.create_function('char_length', 1, len)
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA busy_timeout=30000')
                connection.isolation_level = None
            @event.listens_for(self.engine, 'begin')
            def begin(connection):
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self):
        with self.factory.begin() as session:
            yield session

    def initialize(self):
        with self.transaction() as db:
            if not db.get(Product, DEMO_ID):
                db.add(Product(id=DEMO_ID, source='manual', name='Demo laptop', category='electronics'))

    def require_product(self, db, value, lock=False):
        query = select(Product).where(Product.id == product_uuid(value))
        if lock:
            query = query.with_for_update()
        product = db.scalar(query)
        if product is None:
            raise LookupError('Product not found')
        return product

    def products(self):
        with self.transaction() as db:
            return [{'id': str(p.id), 'name': p.name, 'review_count': count} for p, count in db.execute(
                select(Product, func.count(ReviewRecord.id)).outerjoin(ReviewRecord, ReviewRecord.product_id == Product.id)
                .group_by(Product.id).order_by(Product.created_at))]

    def create_product(self, name):
        with self.transaction() as db:
            p = Product(id=uuid4(), source='manual', name=name, category='electronics')
            db.add(p)
            return {'id': str(p.id), 'name': p.name}

    def analyses(self, db, product_id, version=None, review_ids=None, created_before=None):
        query = select(AnalysisRun.payload).join(ReviewRecord).where(ReviewRecord.product_id == product_id, AnalysisRun.payload.is_not(None))
        if version:
            query = query.where(AnalysisRun.pipeline_version == version)
        if review_ids is not None:
            query = query.where(ReviewRecord.id.in_([UUID(value) for value in review_ids]))
        if created_before is not None:
            query = query.where(AnalysisRun.created_at <= created_before)
        return list(db.scalars(query.order_by(ReviewRecord.submitted_at.desc())))

    def snapshot(self, db, p, version):
        analyses = self.analyses(db, p.id, version)
        rows = [SavedReviewAnalysis(Review(**item['review']), [TagResult(**{**tag, 'sentiment': Sentiment(tag['sentiment'])}) for tag in item['tags']]) for item in analyses]
        payload = asdict(aggregate_saved_analyses(str(p.id), rows))
        payload['_review_ids'] = [item['review']['review_id'] for item in analyses]
        snapshot = ProductSnapshot(id=uuid4(), product_id=p.id, pipeline_version=version,
            aggregate_version=AGGREGATE_VERSION, data_revision=p.data_revision, payload=payload)
        db.add(snapshot)
        db.flush()
        p.current_snapshot_id = snapshot.id
        return snapshot

    def detail(self, value, version, backend):
        with self.transaction() as db:
            p = self.require_product(db, value)
            snapshot = db.get(ProductSnapshot, p.current_snapshot_id) if p.current_snapshot_id else None
            published_version = snapshot.pipeline_version if snapshot else version
            membership = snapshot.payload.get('_review_ids') if snapshot else []
            analyses = self.analyses(db, p.id, published_version, review_ids=membership,
                created_before=snapshot.created_at if snapshot and membership is None else None)
            # Keep the last published evidence visible while a new version runs.
            insights = {key: value for key, value in snapshot.payload.items() if key != '_review_ids'} if snapshot else asdict(aggregate_saved_analyses(str(p.id), []))
            counts = dict(db.execute(select(ReviewRecord.analysis_status, func.count()).where(ReviewRecord.product_id == p.id).group_by(ReviewRecord.analysis_status)).all())
            return {'product': {'id': str(p.id), 'name': p.name}, 'reviews': analyses,
                'insights': insights, 'backend': backend, 'pipeline_version': published_version,
                'requested_pipeline_version': version,
                'snapshot_id': str(snapshot.id) if snapshot else None,
                'aggregate_version': snapshot.aggregate_version if snapshot else AGGREGATE_VERSION,
                'data_revision': snapshot.data_revision if snapshot else 0,
                'stale': bool(counts.get('pending', 0) or counts.get('running', 0) or (snapshot and (snapshot.pipeline_version != version or snapshot.data_revision != p.data_revision))),
                'review_counts': counts}

    def enqueue(self, value, rows, version, key=None, rejected=None):
        rejected = rejected or []
        request_hash = sha256(json.dumps([rows, rejected], sort_keys=True).encode()).hexdigest()
        scope = f'product:{product_uuid(value)}'
        with self.transaction() as db:
            p = self.require_product(db, value, lock=True)
            if key:
                existing = db.scalar(select(IdempotencyRequest).where(IdempotencyRequest.endpoint_scope == scope, IdempotencyRequest.key == key))
                if existing:
                    if existing.request_sha256 != request_hash:
                        raise Conflict('Idempotency key was already used for different content')
                    return str(existing.job_id)
            active = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status.in_(['queued', 'running'])))
            if active >= int(os.environ.get('QUEUE_CAPACITY', '100')):
                raise QueueFull('Processing queue is full; try again after current jobs finish')
            job = ProcessingJob(id=uuid4(), product_id=p.id, type='import', status='queued', stage='queued', pipeline_version=version,
                total_rows=len(rows) + len(rejected), accepted_rows=0, rejected_rows=len(rejected), duplicate_rows=0)
            db.add(job)
            db.flush()
            for error in rejected:
                db.add(JobItem(job_id=job.id, item_key=str(error['row']), status='rejected', error_code='INVALID_ROW', error_summary=error['error'][:500]))
            for number, text in rows:
                dedup = text_hash(text)
                review = db.scalar(select(ReviewRecord).where(ReviewRecord.product_id == p.id, ReviewRecord.dedup_key == dedup))
                if review:
                    job.duplicate_rows += 1
                    continue
                review = ReviewRecord(id=uuid4(), product_id=p.id, source='manual', review_text=text,
                    text_sha256=sha256(text.encode()).hexdigest(), dedup_key=dedup, analysis_status='pending')
                db.add(review)
                db.flush()
                job.accepted_rows += 1
                db.add(JobItem(job_id=job.id, item_key=str(number), review_id=review.id, status='pending'))
            if not job.accepted_rows:
                job.status = 'completed_with_errors' if rejected else 'completed'
                job.stage = 'finished'
            if key:
                db.add(IdempotencyRequest(endpoint_scope=scope, key=key, request_sha256=request_hash, response={'job_id': str(job.id)}, job_id=job.id))
            return str(job.id)

    def job(self, value):
        with self.transaction() as db:
            job = db.get(ProcessingJob, UUID(value))
            if not job:
                raise LookupError('Job not found')
            errors = [{'row': item.item_key, 'error': item.error_summary, 'status': item.status} for item in db.scalars(select(JobItem).where(JobItem.job_id == job.id, JobItem.status.in_(['failed', 'rejected'])))]
            return {**{name: getattr(job, name) for name in ['status', 'stage', 'attempt', 'total_rows', 'accepted_rows', 'rejected_rows', 'duplicate_rows', 'completed_rows', 'failed_rows']},
                'id': str(job.id), 'product_id': str(job.product_id), 'errors': errors,
                'error_summary': job.error_summary, 'pipeline_version': job.pipeline_version}

    def retry(self, value):
        with self.transaction() as db:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == UUID(value)).with_for_update())
            if not job:
                raise LookupError('Job not found')
            if job.status not in ('failed', 'completed_with_errors'):
                raise Conflict('Only finished jobs with failures can be retried')
            items = list(db.scalars(select(JobItem).where(JobItem.job_id == job.id, JobItem.status == 'failed')))
            if not items:
                raise Conflict('No failed inference rows to retry; correct rejected input and import it again')
            for item in items:
                item.status, item.attempt, item.error_summary = 'pending', 0, None
                db.get(ReviewRecord, item.review_id).analysis_status = 'pending'
            job.status, job.stage, job.failed_rows = 'queued', 'queued', 0
            job.leased_by, job.lease_expires_at = None, None
        return self.job(value)

    def claim(self, worker_id, version, lease_seconds=300):
        with self.transaction() as db:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.pipeline_version == version,
                or_(ProcessingJob.status == 'queued', (ProcessingJob.status == 'running') & (ProcessingJob.lease_expires_at < utcnow())))
                .order_by(ProcessingJob.created_at).with_for_update(skip_locked=True).limit(1))
            if not job:
                return None
            job.status, job.stage = 'running', 'analyzing'
            job.leased_by, job.lease_expires_at = worker_id, utcnow() + timedelta(seconds=lease_seconds)
            job.attempt += 1
            return str(job.id)

    def next_item(self, job_id, worker_id):
        with self.transaction() as db:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == UUID(job_id)).with_for_update())
            if job.leased_by != worker_id:
                return None
            job.lease_expires_at = utcnow() + timedelta(seconds=300)
            item = db.scalar(select(JobItem).where(JobItem.job_id == job.id, JobItem.status.in_(['pending', 'running'])).order_by(JobItem.item_key).limit(1))
            if not item:
                if job.completed_rows:
                    p = self.require_product(db, job.product_id, lock=True)
                    snapshot = db.scalar(select(ProductSnapshot).where(ProductSnapshot.product_id == p.id,
                        ProductSnapshot.pipeline_version == job.pipeline_version,
                        ProductSnapshot.aggregate_version == AGGREGATE_VERSION,
                        ProductSnapshot.data_revision == p.data_revision))
                    if snapshot:
                        p.current_snapshot_id = snapshot.id
                    else:
                        self.snapshot(db, p, job.pipeline_version)
                job.status = 'completed_with_errors' if job.failed_rows or job.rejected_rows else 'completed'
                job.stage = 'finished'
                job.leased_by, job.lease_expires_at = None, None
                return None
            if item.attempt >= int(os.environ.get('JOB_MAX_ATTEMPTS', '3')):
                item.status = 'failed'
                item.error_code, item.error_summary = 'LEASE_EXPIRED', 'Worker repeatedly stopped before completing this row'
                db.get(ReviewRecord, item.review_id).analysis_status = 'failed'
                job.failed_rows += 1
                return 'skip', None
            item.status = 'running'
            item.attempt += 1
            review = db.get(ReviewRecord, item.review_id)
            review.analysis_status = 'running'
            return item.item_key, Review(str(review.id), str(review.product_id), review.review_text)

    def finish_item(self, job_id, item_key, worker_id, result=None, error=None):
        with self.transaction() as db:
            job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == UUID(job_id)).with_for_update())
            if job.leased_by != worker_id:
                return
            item = db.get(JobItem, (job.id, item_key))
            if item.status != 'running':
                return
            review = db.get(ReviewRecord, item.review_id)
            if error:
                item.error_code, item.error_summary = 'ANALYSIS_FAILED', str(error)[:500]
                item.status = 'pending' if item.attempt < int(os.environ.get('JOB_MAX_ATTEMPTS', '3')) else 'failed'
                review.analysis_status = item.status
                if item.status == 'failed':
                    job.failed_rows += 1
                return
            existing = db.scalar(select(AnalysisRun).where(AnalysisRun.review_id == review.id, AnalysisRun.pipeline_version == job.pipeline_version))
            if not existing:
                run = AnalysisRun(id=uuid4(), review_id=review.id, pipeline_version=job.pipeline_version, payload=result,
                    original_text_sha256=review.text_sha256, backend=result['backend'], context_policy=result.get('context_policy', 'full_review'), elapsed_ms=result.get('elapsed_ms', 0))
                db.add(run)
                db.flush()
                for tag in result['tags']:
                    db.add(AspectMention(analysis_run_id=run.id, raw_aspect=tag['raw_aspect'],
                        start_char=tag['start_char'], end_char=tag['end_char'],
                        canonical_id=tag.get('normalized_aspect_id'), canonical_label=tag['normalized_aspect'],
                        aspect_confidence=tag['aspect_confidence'], sentiment=tag['sentiment'],
                        sentiment_confidence=tag['sentiment_confidence'], summary_confidence=tag['confidence'],
                        probabilities=tag['probabilities'], normalization_method=tag['normalization_method'],
                        normalization_similarity=tag['normalization_similarity'], tag=tag['tag'],
                        context_start_char=tag['context_start_char'], context_end_char=tag['context_end_char']))
                db.flush()
                p = self.require_product(db, review.product_id, lock=True)
                p.data_revision += 1
            item.status, item.error_code, item.error_summary = 'completed', None, None
            review.analysis_status = 'completed'
            job.completed_rows += 1

    def heartbeat(self, worker_id, version, job_id=None, preview_id=None):
        with self.transaction() as db:
            status = db.get(WorkerStatus, worker_id)
            if not status:
                status = WorkerStatus(worker_id=worker_id, pipeline_version=version, model_health='ready')
                db.add(status)
            status.heartbeat, status.busy = utcnow(), bool(job_id or preview_id)
            if job_id:
                job = db.get(ProcessingJob, UUID(job_id))
                if job and job.leased_by == worker_id:
                    job.lease_expires_at = utcnow() + timedelta(seconds=300)
            if preview_id:
                preview = db.get(AnalysisPreview, UUID(preview_id))
                if preview and preview.leased_by == worker_id:
                    preview.lease_expires_at = utcnow() + timedelta(seconds=300)

    def claim_preview(self, worker_id, version):
        with self.transaction() as db:
            item = db.scalar(select(AnalysisPreview).where(AnalysisPreview.pipeline_version == version,
                AnalysisPreview.expires_at > utcnow(),
                or_(AnalysisPreview.status == 'queued', (AnalysisPreview.status == 'running') & (AnalysisPreview.lease_expires_at < utcnow())))
                .order_by(AnalysisPreview.created_at).with_for_update(skip_locked=True).limit(1))
            if not item:
                return None
            item.status, item.leased_by = 'running', worker_id
            item.lease_expires_at = utcnow() + timedelta(seconds=300)
            return str(item.id), Review(str(item.id), str(item.product_id), item.review_text)

    def finish_preview(self, preview_id, worker_id, result=None, error=None):
        with self.transaction() as db:
            item = db.scalar(select(AnalysisPreview).where(AnalysisPreview.id == UUID(preview_id)).with_for_update())
            if item.leased_by != worker_id:
                return
            item.status = 'failed' if error else 'completed'
            item.analysis = {'error': str(error)[:500]} if error else result
            item.leased_by, item.lease_expires_at = None, None

    def regenerate(self, value, version):
        """Analyze previously saved reviews missing the current immutable version."""
        with self.transaction() as db:
            p = self.require_product(db, value, lock=True)
            active = db.scalar(select(ProcessingJob).where(ProcessingJob.product_id == p.id,
                ProcessingJob.pipeline_version == version, ProcessingJob.status.in_(['queued', 'running'])))
            if active:
                return str(active.id)
            reviews = list(db.scalars(select(ReviewRecord).where(ReviewRecord.product_id == p.id,
                ~select(AnalysisRun.id).where(AnalysisRun.review_id == ReviewRecord.id, AnalysisRun.pipeline_version == version).exists())))
            job = ProcessingJob(id=uuid4(), product_id=p.id, type='regeneration', status='queued' if reviews else 'completed',
                stage='queued' if reviews else 'finished', pipeline_version=version,
                total_rows=len(reviews), accepted_rows=len(reviews), rejected_rows=0, duplicate_rows=0)
            db.add(job)
            db.flush()
            for number, review in enumerate(reviews, 1):
                review.analysis_status = 'pending'
                db.add(JobItem(job_id=job.id, item_key=str(number), review_id=review.id, status='pending'))
            return str(job.id)
