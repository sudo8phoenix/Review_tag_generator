"""HTTP-to-storage verification with durable workers, without model downloads."""
from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, func

from backend.app.db.models import ProcessingJob, JobItem, ProductSnapshot, ReviewRecord, utcnow
from backend.app.main import app
from backend.app.repository import Repository, Conflict
from backend.app.worker import Worker
from review_tag_generator import ReviewAnalyzer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_DATABASE', str(tmp_path / 'app.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('DEMO_MODEL_BACKEND', 'heuristic')
    monkeypatch.setenv('RUN_EMBEDDED_WORKER', '0')
    with TestClient(app) as client:
        app.state.worker = Worker(app.state.repository, ReviewAnalyzer(use_transformer=False))
        yield client


def finish(client):
    while app.state.worker.run_once():
        pass


def test_preview_is_unsaved_and_submission_is_idempotent(client):
    preview = client.post('/api/demo/products/demo-laptop/preview', json={'reviews': ['Great display.']})
    assert preview.status_code == 200
    preview_id = preview.json()['preview_ids'][0]
    assert client.get(f'/api/demo/previews/{preview_id}').json()['status'] == 'queued'
    finish(client)
    assert client.get(f'/api/demo/previews/{preview_id}').json()['analysis']['tags']
    assert client.get('/api/demo/products/demo-laptop').json()['reviews'] == []
    headers = {'Idempotency-Key': 'save-1'}
    payload = {'reviews': ['Great display.']}
    response = client.post('/api/demo/products/demo-laptop/jobs', json=payload, headers=headers)
    assert response.status_code == 202
    job = response.json()
    assert client.post('/api/demo/products/demo-laptop/jobs', json=payload, headers=headers).json()['id'] == job['id']
    assert client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Different battery.']}, headers=headers).status_code == 409
    finish(client)
    detail = client.get('/api/demo/products/demo-laptop').json()
    assert len(detail['reviews']) == 1
    assert detail['data_revision'] == 1
    assert detail['snapshot_id']
    assert not detail['stale']
    duplicate = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['  GREAT   display. ']}).json()
    assert duplicate['duplicate_rows'] == 1
    assert duplicate['accepted_rows'] == 0
    assert client.get(f"/api/demo/jobs/{job['id']}").json()['completed_rows'] == 1


def test_import_partial_failure_duplicates_and_error_export(client):
    response = client.post('/api/demo/products/demo-laptop/imports', json={
        'filename': 'amazon.jsonl', 'content': '{"reviewText":"Excellent keyboard."}\ninvalid\n{"text":"Excellent keyboard."}\n{"text":"Poor battery."}'})
    assert response.status_code == 202
    job = response.json()
    assert (job['total_rows'], job['accepted_rows'], job['rejected_rows'], job['duplicate_rows']) == (4, 2, 1, 1)
    finish(client)
    job = client.get(f"/api/demo/jobs/{job['id']}").json()
    assert job['status'] == 'completed_with_errors'
    assert job['completed_rows'] == 2
    assert job['errors'][0]['row'] == '2'
    export = client.get(f"/api/demo/jobs/{job['id']}/errors.csv")
    assert export.status_code == 200
    assert 'INVALID_ROW' not in export.text
    assert 'review_text must contain' in export.text
    assert client.post(f"/api/demo/jobs/{job['id']}/retry").status_code == 409
    assert client.post('/api/demo/products/demo-laptop/imports', json={'filename': 'x.csv', 'content': 'wrong\ntext'}).status_code == 422


def test_automatic_retry_then_manual_recovery(client):
    analyzer = app.state.worker.analyzer
    original = analyzer.analyze
    def failure(review):
        raise RuntimeError('Transient model failure')
    analyzer.analyze = failure
    job = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']}).json()
    finish(client)
    status = client.get(f"/api/demo/jobs/{job['id']}").json()
    assert status['failed_rows'] == 1
    with app.state.repository.transaction() as db:
        assert db.scalar(select(JobItem)).attempt == 3
    analyzer.analyze = original
    assert client.post(f"/api/demo/jobs/{job['id']}/retry").status_code == 202
    finish(client)
    assert client.get(f"/api/demo/jobs/{job['id']}").json()['status'] == 'completed'
    assert len(client.get('/api/demo/products/demo-laptop').json()['reviews']) == 1


def test_restart_lease_recovery_and_snapshot_history(client):
    repository = app.state.repository
    version = app.state.version
    job = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.', 'Poor battery.']}).json()
    assert repository.claim('crashed-worker', version) == job['id']
    item_key, _ = repository.next_item(job['id'], 'crashed-worker')
    with repository.transaction() as db:
        db.get(ProcessingJob, UUID(job['id'])).lease_expires_at = utcnow() - timedelta(seconds=1)
    # New repository and worker imitate a process restart, using persisted state.
    replacement = Repository(str(repository.engine.url))
    worker = Worker(replacement, ReviewAnalyzer(use_transformer=False))
    assert worker.run_once()
    assert repository.job(job['id'])['completed_rows'] == 2
    assert repository.job(job['id'])['status'] == 'completed'
    with repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ProductSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(ReviewRecord)) == 2
    replacement.engine.dispose()


def test_metrics_and_validation(client):
    health = client.get('/api/health').json()
    assert health['context_policy'] == 'local_clause'
    assert health['evaluated_context_policy'] == 'full_review'
    metrics = client.get('/api/models/metrics').json()
    assert metrics['human_normalization_gate'] == 'pending'
    assert 'current/test' in metrics['records']
    assert client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': [' ']}).status_code == 422
    assert client.get('/api/demo/jobs/invalid').status_code == 422
    assert client.get('/api/demo/products/missing').status_code == 404


def test_preview_expiry_queue_capacity_and_readiness(client, monkeypatch):
    from backend.app.db.models import AnalysisPreview
    monkeypatch.setenv('QUEUE_CAPACITY', '1')
    assert client.get('/api/ready').status_code == 503
    first = client.post('/api/demo/products/demo-laptop/preview', json={'reviews': ['Great display.']}).json()
    assert client.post('/api/demo/products/demo-laptop/preview', json={'reviews': ['Poor battery.']}).status_code == 429
    finish(client)
    assert client.get('/api/ready').status_code == 200
    with app.state.repository.transaction() as db:
        db.get(AnalysisPreview, UUID(first['preview_ids'][0])).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get(f"/api/demo/previews/{first['preview_ids'][0]}").status_code == 410
    queued = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']}, headers={'Idempotency-Key': 'capacity'})
    assert queued.status_code == 202
    assert client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']}, headers={'Idempotency-Key': 'capacity'}).json()['id'] == queued.json()['id']
    assert client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Poor battery.']}).status_code == 429
    assert client.post('/api/demo/products/bad-id/preview', json={'reviews': ['Great display.']}).status_code == 404


def test_regeneration_preserves_immutable_runs_and_versions(client):
    from backend.app.db.models import AnalysisRun
    client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']})
    finish(client)
    original = client.get('/api/demo/products/demo-laptop').json()
    repository = app.state.repository
    next_version = 'a' * 64
    regenerated = repository.regenerate('demo-laptop', next_version)
    worker = Worker(repository, ReviewAnalyzer(use_transformer=False))
    worker.version = next_version
    assert worker.run_once()
    assert repository.job(regenerated)['completed_rows'] == 1
    new_detail = repository.detail('demo-laptop', next_version, 'heuristic')
    assert new_detail['snapshot_id'] != original['snapshot_id']
    assert new_detail['data_revision'] == 2
    with repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 2
        assert db.scalar(select(func.count()).select_from(ProductSnapshot)) == 2
    assert repository.job(repository.regenerate('demo-laptop', next_version))['total_rows'] == 0
    assert repository.detail('demo-laptop', app.state.version, 'heuristic')['stale']


def test_detail_keeps_published_evidence_and_revision_during_import(client):
    client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']})
    finish(client)
    published = client.get('/api/demo/products/demo-laptop').json()
    worker = app.state.worker
    repository = app.state.repository
    job = repository.enqueue('demo-laptop', [(1, 'Poor battery.'), (2, 'Excellent keyboard.')], worker.version)
    assert repository.claim(worker.id, worker.version) == job
    key, review = repository.next_item(job, worker.id)
    result = worker.analyzer.analyze(review)
    repository.finish_item(job, key, worker.id, result=result)
    pending = client.get('/api/demo/products/demo-laptop').json()
    assert pending['stale']
    assert pending['reviews'] == published['reviews']
    assert pending['insights'] == published['insights']
    assert pending['data_revision'] == published['data_revision']
    worker.process_job(job)
    completed = client.get('/api/demo/products/demo-laptop').json()
    assert len(completed['reviews']) == completed['insights']['review_count'] == 3
    assert completed['data_revision'] == 3
    assert not completed['stale']


def test_previews_arriving_during_bulk_run_before_next_review(client):
    worker = app.state.worker
    original = worker.analyzer.analyze
    order, preview_ids = [], []

    def analyze(review):
        order.append(review.review_text)
        if len(order) == 1:
            response = client.post('/api/demo/products/demo-laptop/preview', json={'reviews': ['Great screen.']})
            preview_ids.extend(response.json()['preview_ids'])
        return original(review)

    worker.analyzer.analyze = analyze
    job = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.', 'Poor battery.']}).json()
    assert worker.run_once()
    assert order == ['Great display.', 'Great screen.', 'Poor battery.']
    assert client.get(f'/api/demo/previews/{preview_ids[0]}').json()['status'] == 'completed'
    assert app.state.repository.job(job['id'])['status'] == 'completed'


def test_external_worker_startup_does_not_load_models(tmp_path, monkeypatch):
    import backend.app.main as main_module
    monkeypatch.setenv('DEMO_DATABASE', str(tmp_path / 'external.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('DEMO_MODEL_BACKEND', 'transformer')
    monkeypatch.setenv('RUN_EMBEDDED_WORKER', '0')

    def forbidden():
        raise AssertionError('API must not construct an inference model')

    monkeypatch.setattr(main_module, 'make_analyzer', forbidden)
    with TestClient(app) as external:
        assert app.state.worker is None
        assert external.get('/api/health').json()['backend'] == 'transformer'
        assert external.get('/api/ready').status_code == 503
        assert external.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.']}).status_code == 202


def test_evidence_audit_uses_published_snapshot(client):
    response = client.get('/api/demo/products/demo-laptop/evidence-audit')
    assert response.json()['aspects'] == []
    client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': ['Great display.', 'Excellent display.', 'Amazing display.']})
    finish(client)
    detail = client.get('/api/demo/products/demo-laptop').json()
    audit = client.get('/api/demo/products/demo-laptop/evidence-audit').json()
    assert audit['snapshot_id'] == detail['snapshot_id']
    assert audit['data_revision'] == detail['data_revision']
    assert audit['aspects'][0]['fragile_tag']
    assert audit['aspects'][0]['tag_stability'] == 0
    assert client.get('/api/demo/products/missing/evidence-audit').status_code == 404
