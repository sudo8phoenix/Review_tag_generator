"""Correction workflow against actual HTTP, worker and SQLite persistence."""
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from backend.app import llm_provider
from backend.app.db.models import ReviewCorrection, ReviewSuggestion
from backend.app.main import app
from backend.app.repository import Repository
from backend.app.worker import Worker
from review_tag_generator import ReviewAnalyzer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_DATABASE', str(tmp_path / 'corrections.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('DEMO_MODEL_BACKEND', 'heuristic')
    monkeypatch.setenv('RUN_EMBEDDED_WORKER', '0')
    monkeypatch.setenv('LLM_PROVIDER', 'groq')
    monkeypatch.setenv('GROQ_API_KEY', 'test-injected-no-network')
    monkeypatch.setenv('LLM_MODEL', 'test-model')
    monkeypatch.setattr(llm_provider, 'generate_structured', lambda *_args: {
        'canonical_aspect_id': 'display', 'proposed_aspect_label': None,
        'explanation': 'Screen describes the display.'})
    with TestClient(app) as client:
        analyzer = ReviewAnalyzer(use_transformer=False)
        original = analyzer.analyze

        def explicit_unknown_fixture(review):
            result = original(review)
            for tag in result['tags']:
                if tag['raw_aspect'].casefold() == 'screen':
                    tag.update(normalized_aspect=None, normalized_aspect_id=None,
                               normalization_method='unknown', normalization_similarity=None, tag=None)
            return result

        analyzer.analyze = explicit_unknown_fixture
        app.state.worker = Worker(app.state.repository, analyzer)
        yield client


def finish():
    while app.state.worker.run_once():
        pass


def saved(client, product='demo-laptop', text='Great screen. Poor battery.'):
    assert client.post(f'/api/demo/products/{product}/jobs', json={'reviews': [text]}).status_code == 202
    finish()
    detail = client.get(f'/api/demo/products/{product}').json()
    review = next(row for row in detail['reviews'] if row['review']['review_text'] == text)
    tag = review['tags'][0]
    reference = {'snapshot_id': detail['snapshot_id'], 'review_id': review['review']['review_id'],
                 'start_char': tag['start_char'], 'end_char': tag['end_char']}
    return detail, reference


def body(reference, **overrides):
    return {**reference, 'request_id': str(uuid4()), 'decision': 'edited',
            'reviewer': 'Reviewer A', 'reason': 'The review evaluates screen quality.',
            'canonical_id': 'display', 'sentiment': 'negative', **overrides}


def suggest(client, reference, product='demo-laptop'):
    response = client.post(f'/api/demo/products/{product}/corrections/suggest', json=reference)
    assert response.status_code == 200, response.text
    return response.json()


def decision(reference, suggestion, action, **overrides):
    return {**reference, 'request_id': str(uuid4()), 'decision': action,
            'reviewer': 'Reviewer B', 'reason': 'Checked the source phrase in context.',
            'suggestion_id': suggestion['id'], **overrides}


def history(client, reference):
    return client.get('/api/demo/products/demo-laptop/corrections/history', params=reference)


def test_accept_and_export_retain_server_suggestion_and_original_predictions(client):
    before, reference = saved(client)
    suggestion = suggest(client, reference)
    response = client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, suggestion, 'accepted'))
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['original']['normalized_aspect_id'] is None
    assert row['resolution'] == {'supported': True, 'canonical_id': 'display',
                                 'proposed_aspect_label': None, 'sentiment': 'positive'}
    assert row['suggestion']['provider'] == 'groq' and row['suggestion']['model'] == 'test-model'
    assert row['pipeline_version'] == before['pipeline_version']
    assert not row['applied_to_predictions']
    assert client.get('/api/demo/products/demo-laptop').json() == before
    exported = client.get('/api/demo/products/demo-laptop/corrections').json()['items']
    assert exported[0]['review_text'] == 'Great screen. Poor battery.'
    assert exported[0]['id'] == row['id']


def test_edits_and_rejections_are_append_only_and_survive_repository_reopen(client):
    before, reference = saved(client)
    suggestion = suggest(client, reference)
    rejected = client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, suggestion, 'rejected')).json()
    assert rejected['resolution'] is None
    corrected = client.post('/api/demo/products/demo-laptop/corrections', json=body(reference,
        expected_previous_id=rejected['id'], suggestion_id=suggestion['id'])).json()
    assert corrected['resolution']['sentiment'] == 'negative'
    assert corrected['previous_id'] == rejected['id']
    assert [r['id'] for r in history(client, reference).json()['items']] == [corrected['id'], rejected['id']]
    reopened = Repository(str(app.state.repository.engine.url))
    try:
        with reopened.transaction() as db:
            assert db.scalar(select(func.count()).select_from(ReviewCorrection)) == 2
    finally:
        reopened.engine.dispose()
    assert client.get('/api/demo/products/demo-laptop').json() == before


def test_retry_is_idempotent_but_changed_payload_and_stale_head_conflict(client):
    _, reference = saved(client)
    request = body(reference)
    first = client.post('/api/demo/products/demo-laptop/corrections', json=request)
    assert client.post('/api/demo/products/demo-laptop/corrections', json=request).json() == first.json()
    assert client.post('/api/demo/products/demo-laptop/corrections', json={**request, 'reason': 'Changed'}).status_code == 409
    assert client.post('/api/demo/products/demo-laptop/corrections', json=body(reference)).status_code == 409
    assert len(history(client, reference).json()['items']) == 1


@pytest.mark.parametrize('overrides', [
    {'reviewer': '  '}, {'reason': '  '}, {'canonical_id': 'invented'},
    {'start_char': 0, 'end_char': 999}, {'start_char': True}, {'sentiment': 'mixed'},
    {'decision': 'accepted'}, {'supported': False, 'sentiment': 'negative'},
])
def test_invalid_decisions_fail_without_writes(client, overrides):
    _, reference = saved(client)
    assert client.post('/api/demo/products/demo-laptop/corrections', json=body(reference, **overrides)).status_code == 422
    assert history(client, reference).json()['items'] == []


def test_unknown_and_unsupported_decisions_are_distinct(client):
    _, reference = saved(client)
    unknown = client.post('/api/demo/products/demo-laptop/corrections', json=body(reference, canonical_id=None)).json()
    assert unknown['resolution']['supported'] and unknown['resolution']['canonical_id'] is None
    unsupported = client.post('/api/demo/products/demo-laptop/corrections', json=body(reference,
        expected_previous_id=unknown['id'], supported=False, canonical_id=None, sentiment=None)).json()
    assert unsupported['resolution'] == {'supported': False, 'canonical_id': None,
                                        'proposed_aspect_label': None, 'sentiment': None}


def test_cross_product_and_cross_span_suggestions_are_rejected(client):
    _, reference = saved(client)
    other = client.post('/api/demo/products', json={'name': 'Other'}).json()['id']
    _, other_reference = saved(client, other)
    suggestion = suggest(client, other_reference, other)
    assert client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, suggestion, 'accepted')).status_code == 422
    assert client.get(f'/api/demo/products/{other}/corrections/history', params=reference).status_code == 409
    suggestion = suggest(client, reference)
    battery_reference = {**reference, 'start_char': 19, 'end_char': 26}
    assert client.post('/api/demo/products/demo-laptop/corrections', json=decision(battery_reference, suggestion, 'accepted')).status_code == 422
    assert history(client, reference).json()['items'] == []


def test_changed_snapshot_rejects_stale_decision(client):
    _, reference = saved(client)
    saved(client, text='Great keyboard.')
    assert client.post('/api/demo/products/demo-laptop/corrections', json=body(reference)).status_code == 409
    assert history(client, reference).status_code == 409


def test_suggestion_call_rechecks_snapshot_before_persisting(client, monkeypatch):
    _, reference = saved(client)

    def changing_snapshot(*_args):
        saved(client, text='Great keyboard.')
        return {'canonical_aspect_id': 'display', 'proposed_aspect_label': None, 'explanation': 'Display.'}

    monkeypatch.setattr(llm_provider, 'generate_structured', changing_snapshot)
    assert client.post('/api/demo/products/demo-laptop/corrections/suggest', json=reference).status_code == 409
    with app.state.repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewSuggestion)) == 0


def test_accept_proposed_category_does_not_extend_ontology_and_abstention_cannot_be_accepted(client, monkeypatch):
    _, reference = saved(client)
    monkeypatch.setattr(llm_provider, 'generate_structured', lambda *_args: {
        'canonical_aspect_id': None, 'proposed_aspect_label': 'Screen coating', 'explanation': 'Needs a new category.'})
    suggestion = suggest(client, reference)
    accepted = client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, suggestion, 'accepted')).json()
    assert accepted['resolution']['proposed_aspect_label'] == 'Screen coating'
    assert 'Screen coating' not in str(client.get('/api/corrections/options').json())
    monkeypatch.setattr(llm_provider, 'generate_structured', lambda *_args: {
        'canonical_aspect_id': None, 'proposed_aspect_label': None, 'explanation': 'Insufficient context.'})
    abstention = suggest(client, reference)
    assert client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, abstention, 'accepted',
        expected_previous_id=accepted['id'])).status_code == 422


def test_removal_cascades_corrections_and_suggestions_without_other_product_loss(client):
    _, reference = saved(client)
    suggestion = suggest(client, reference)
    client.post('/api/demo/products/demo-laptop/corrections', json=decision(reference, suggestion, 'accepted'))
    other = client.post('/api/demo/products', json={'name': 'Other'}).json()['id']
    _, other_reference = saved(client, other)
    client.post(f'/api/demo/products/{other}/corrections', json=body(other_reference))
    assert client.delete('/api/demo/products/demo-laptop/saved-data').status_code == 200
    with app.state.repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewSuggestion)) == 0
        assert db.scalar(select(func.count()).select_from(ReviewCorrection)) == 1
    assert len(client.get(f'/api/demo/products/{other}/corrections').json()['items']) == 1


def test_unicode_offsets_and_known_sentiment_correction(client):
    _, reference = saved(client, text='😀 Great battery.')
    assert reference['start_char'] == 8
    response = client.post('/api/demo/products/demo-laptop/corrections', json=body(reference, canonical_id='battery'))
    assert response.status_code == 201
    assert response.json()['original']['raw_aspect'] == 'battery'
    assert client.post('/api/demo/products/demo-laptop/corrections/suggest', json=reference).status_code == 422
