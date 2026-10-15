"""Verify the shipped HTTP/worker/database path with the trained checkpoints."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.worker import Worker, make_analyzer


@pytest.mark.model
def test_trained_preview_and_durable_save_use_frozen_policy(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_DATABASE', str(tmp_path / 'trained.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('DEMO_MODEL_BACKEND', 'transformer')
    monkeypatch.setenv('RUN_EMBEDDED_WORKER', '0')
    text = 'Amazing display but terrible battery.'
    with TestClient(app) as client:
        app.state.worker = Worker(app.state.repository, make_analyzer())
        assert client.get('/api/health').json()['context_policy'] == 'full_review'
        preview_id = client.post('/api/demo/products/demo-laptop/preview', json={'reviews': [text]}).json()['preview_ids'][0]
        assert app.state.worker.run_once()
        preview = client.get(f'/api/demo/previews/{preview_id}').json()['analysis']
        assert preview['context_policy'] == 'full_review'
        assert preview['backend'] == 'transformer'
        assert client.get('/api/demo/products/demo-laptop').json()['reviews'] == []
        job = client.post('/api/demo/products/demo-laptop/jobs', json={'reviews': [text]}).json()
        assert app.state.worker.run_once()
        assert client.get(f"/api/demo/jobs/{job['id']}").json()['status'] == 'completed'
        detail = client.get('/api/demo/products/demo-laptop').json()
        saved = detail['reviews'][0]
        assert saved['tags'] == preview['tags']
        assert {tag['raw_aspect'] for tag in saved['tags']} == {'display', 'battery'}
        for tag in saved['tags']:
            assert text[tag['start_char']:tag['end_char']] == tag['raw_aspect']
            assert tag['context_start_char'] <= tag['start_char'] < tag['end_char'] <= tag['context_end_char']
            assert sum(tag['probabilities'].values()) == pytest.approx(1, abs=1e-5)
        assert detail['insights']['review_count'] == 1
        assert detail['snapshot_id'] and not detail['stale']
