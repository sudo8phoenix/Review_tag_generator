"""Review analysis API backed by transactional repositories and durable jobs."""
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
import csv
import io
import json
import os
from pathlib import Path
from threading import Thread
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func

from backend.app.db.models import AnalysisPreview, WorkerStatus, utcnow
from backend.app.imports import parse_import, validate_rows
from backend.app.repository import Repository, Conflict, QueueFull, pipeline_version
from backend.app.worker import Worker, make_analyzer, runtime_metadata

ROOT = Path(__file__).resolve().parents[2]


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Name cannot be blank')
        return value.strip()


class ReviewsInput(BaseModel):
    reviews: list[str] = Field(min_length=1, max_length=100)

    @field_validator('reviews')
    @classmethod
    def valid_reviews(cls, values):
        if any(not text.strip() or len(text) > 10000 for text in values):
            raise ValueError('Each review must contain 1–10000 characters')
        return values


class ImportInput(BaseModel):
    filename: str = Field(max_length=255)
    content: str = Field(max_length=10 * 1024 * 1024)


@asynccontextmanager
async def lifespan(application):
    repository = Repository()
    repository.initialize()
    backend, context_policy = runtime_metadata()
    application.state.repository = repository
    application.state.backend = backend
    application.state.context_policy = context_policy
    application.state.version = pipeline_version(backend)
    application.state.worker = None
    worker = None
    thread = None
    if os.environ.get('RUN_EMBEDDED_WORKER', '1') == '1':
        worker = Worker(repository, make_analyzer())
        application.state.worker = worker
        thread = Thread(target=worker.run, daemon=True, name='review-worker')
        thread.start()
    yield
    if worker:
        worker.stop.set()
    if thread:
        thread.join(timeout=10)
    repository.engine.dispose()


app = FastAPI(title='Review Tag Generator', lifespan=lifespan)


@app.middleware('http')
async def limit_request_body(request: Request, call_next):
    # Also count streamed bodies; Content-Length alone is not a trustworthy bound.
    if request.method in ('POST', 'PUT', 'PATCH'):
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 12 * 1024 * 1024:
                return Response('Request exceeds 12 MiB', status_code=413)
            chunks.append(chunk)
        request._body = b''.join(chunks)
    return await call_next(request)


@app.exception_handler(LookupError)
async def not_found(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={'detail': str(exc)})


@app.exception_handler(Conflict)
async def conflict(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.get('/api/health')
def health():
    with app.state.repository.transaction() as db:
        db.execute(select(1))
        ready = bool(db.scalar(select(WorkerStatus.worker_id).where(WorkerStatus.pipeline_version == app.state.version, WorkerStatus.heartbeat > utcnow() - timedelta(seconds=30)).limit(1)))
    return {'status': 'ok', 'worker_ready': ready, 'backend': app.state.backend,
        'storage': app.state.repository.storage, 'context_policy': app.state.context_policy, 'evaluated_context_policy': 'full_review',
        'pipeline_version': app.state.version}


@app.get('/api/ready')
def ready():
    status = health()
    if not status['worker_ready']:
        raise HTTPException(503, 'No current worker heartbeat; queued work remains durable')
    return status


@app.get('/api/demo/products')
def products():
    return app.state.repository.products()


@app.post('/api/demo/products', status_code=201)
def create_product(body: ProductInput):
    return app.state.repository.create_product(body.name)


@app.get('/api/demo/products/{product_id}')
def detail(product_id: str):
    try:
        return app.state.repository.detail(product_id, app.state.version, app.state.backend)
    except ValueError as exc:
        raise HTTPException(404, 'Product not found') from exc


@app.get('/api/demo/products/{product_id}/evidence-audit')
def evidence_audit(product_id: str):
    from review_tag_generator.evidence_audit import audit_evidence
    published = app.state.repository.detail(product_id, app.state.version, app.state.backend)
    return {**audit_evidence(published['insights']),
        **{key: published[key] for key in ('snapshot_id', 'pipeline_version', 'aggregate_version', 'data_revision', 'stale')}}


@app.post('/api/demo/products/{product_id}/preview')
def preview(product_id: str, body: ReviewsInput):
    repository = app.state.repository
    with repository.transaction() as db:
        product = repository.require_product(db, product_id)
        pid = product.id
    ids = []
    with repository.transaction() as db:
        count = db.scalar(select(func.count()).select_from(AnalysisPreview).where(AnalysisPreview.status.in_(['queued', 'running']), AnalysisPreview.expires_at > utcnow()))
        if count + len(body.reviews) > int(os.environ.get('QUEUE_CAPACITY', '100')):
            raise HTTPException(429, 'Preview queue is full; try again after current previews finish')
        for text in body.reviews:
            item = AnalysisPreview(id=uuid4(), product_id=pid, review_text=text,
                text_sha256=__import__('hashlib').sha256(text.encode()).hexdigest(),
                status='queued', pipeline_version=app.state.version, expires_at=utcnow() + timedelta(minutes=30))
            db.add(item)
            ids.append(str(item.id))
    return {'analyses': [], 'preview_ids': ids}



@app.get('/api/demo/previews/{preview_id}')
def get_preview(preview_id: UUID):
    with app.state.repository.transaction() as db:
        item = db.get(AnalysisPreview, preview_id)
        if not item:
            raise HTTPException(404, 'Preview not found')
        expiry = item.expires_at.replace(tzinfo=timezone.utc)
        if expiry < utcnow():
            raise HTTPException(410, 'Preview expired; analyze the preserved draft again')
        return {'id': str(item.id), 'status': item.status, 'analysis': item.analysis, 'expires_at': expiry, 'error_summary': item.analysis.get('error') if item.status == 'failed' and item.analysis else None}


def enqueue(product_id, rows, errors, key):
    if key and (len(key) > 64 or not key.strip()):
        raise HTTPException(422, 'Idempotency-Key must contain 1–64 characters')
    try:
        job_id = app.state.repository.enqueue(product_id, rows, app.state.version, key, errors)
    except ValueError as exc:
        if isinstance(exc, Conflict):
            raise
        if isinstance(exc, QueueFull):
            raise HTTPException(429, str(exc)) from exc
        raise HTTPException(422, str(exc)) from exc
    return app.state.repository.job(job_id)


@app.post('/api/demo/products/{product_id}/jobs', status_code=202)
@app.post('/api/demo/products/{product_id}/reviews', status_code=202)
def submit(product_id: str, body: ReviewsInput, idempotency_key: str | None = Header(default=None)):
    rows, errors = validate_rows(body.reviews)
    return enqueue(product_id, rows, errors, idempotency_key)


@app.post('/api/demo/imports/validate')
def validate_import(body: ImportInput):
    try:
        rows, errors = parse_import(body.filename, body.content)
    except (ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'reviews': [text for _, text in rows], 'errors': errors, 'total_rows': len(rows) + len(errors)}


@app.post('/api/demo/products/{product_id}/imports', status_code=202)
def import_reviews(product_id: str, body: ImportInput, idempotency_key: str | None = Header(default=None)):
    try:
        rows, errors = parse_import(body.filename, body.content)
    except (ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc)) from exc
    return enqueue(product_id, rows, errors, idempotency_key)


@app.post('/api/demo/products/{product_id}/regenerate', status_code=202)
def regenerate(product_id: str):
    job_id = app.state.repository.regenerate(product_id, app.state.version)
    return app.state.repository.job(job_id)


@app.get('/api/demo/jobs/{job_id}')
def job_status(job_id: UUID):
    return app.state.repository.job(str(job_id))


@app.post('/api/demo/jobs/{job_id}/retry', status_code=202)
def retry(job_id: UUID):
    return app.state.repository.retry(str(job_id))


@app.get('/api/demo/jobs/{job_id}/errors.csv')
def job_errors(job_id: UUID):
    job = app.state.repository.job(str(job_id))
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['row', 'status', 'error'])
    writer.writeheader()
    for error in job['errors']:
        # Prevent spreadsheet formula execution in downloaded error messages.
        writer.writerow({k: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v for k, v in error.items()})
    return Response(stream.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="job-{job_id}-errors.csv"'})


@app.get('/api/models/metrics')
def metrics():
    records = {}
    for name in ['current/validation', 'current/test', 'current/normalization-fixture-report', 'current/policy', 'A2/aspect_test', 'A3/sentiment_test']:
        path = ROOT / 'audit/evidence' / f'{name}.json'
        if path.exists():
            records[name] = json.loads(path.read_text())
    return {'pipeline_version': app.state.version, 'context_policy': 'full_review',
        'backend': app.state.backend, 'records': records,
        'human_normalization_gate': 'pending',
        'note': 'Recorded evaluations describe their named frozen runs. Synthetic normalization scores are development evidence, not a human-reviewed release score.'}
