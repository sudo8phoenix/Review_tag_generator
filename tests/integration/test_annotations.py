"""Whole-review annotations, progress, missing spans and source integrity."""
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from backend.app.db.models import ReviewAnnotation
from backend.app.main import app
from backend.app.repository import Repository
from backend.app.worker import Worker
from review_tag_generator import ReviewAnalyzer

BASE = '/api/demo/products/demo-laptop/annotations'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_DATABASE', str(tmp_path / 'annotations.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('DEMO_MODEL_BACKEND', 'heuristic')
    monkeypatch.setenv('RUN_EMBEDDED_WORKER', '0')
    with TestClient(app) as client:
        app.state.worker = Worker(app.state.repository, ReviewAnalyzer(use_transformer=False))
        yield client


def saved(client, texts=None, product='demo-laptop'):
    texts = texts or ['😀 Great battery life; wifi is poor.', 'Nothing to report.']
    response = client.post(f'/api/demo/products/{product}/jobs', json={'reviews': texts})
    assert response.status_code == 202
    while app.state.worker.run_once():
        pass
    detail = client.get(f'/api/demo/products/{product}').json()
    return detail


def reference(detail, text):
    review = next(row for row in detail['reviews'] if row['review']['review_text'] == text)
    return {'snapshot_id': detail['snapshot_id'], 'review_id': review['review']['review_id']}


def annotation(client, ref):
    response = client.get(f"{BASE}/{ref['review_id']}", params={'snapshot_id': ref['snapshot_id']})
    assert response.status_code == 200, response.text
    return response.json()


def body(detail, **updates):
    return {'snapshot_id': detail['snapshot_id'], 'review_id': detail['review_id'],
        'request_id': str(uuid4()), 'expected_previous_id': detail['latest_id'],
        'expected_correction_id': detail['correction_revision'], 'status': 'reviewed',
        'reviewer': 'Reviewer A', 'reason': 'Checked every explicit feature in the original review.',
        'mentions': deepcopy(detail['mentions']), 'confirmed_no_aspects': False, **updates}


def test_worklist_counts_all_published_reviews_including_zero_detections(client):
    assert client.get(BASE).json()['summary'] == {'total': 0, 'needs_review': 0, 'reviewed': 0, 'needs_adjudication': 0}
    detail = saved(client)
    result = client.get(BASE, params={'snapshot_id': detail['snapshot_id']}).json()
    assert result['summary'] == {'total': 2, 'needs_review': 2, 'reviewed': 0, 'needs_adjudication': 0}
    assert any(item['model_mentions'] == 0 for item in result['items'])
    assert client.get(BASE, params={'status': 'reviewed'}).json()['items'] == []
    assert client.get(BASE, params={'status': 'invented'}).status_code == 422


def test_add_missing_aspect_adjust_boundary_and_preserve_original_predictions(client):
    before = saved(client)
    text = '😀 Great battery life; wifi is poor.'
    draft = annotation(client, reference(before, text))
    assert draft['mentions'][0]['raw_aspect'] == 'battery life'
    assert draft['mentions'][0]['start_char'] == 8
    battery = {**draft['mentions'][0], 'raw_aspect': 'battery', 'end_char': 15}
    wifi = {'raw_aspect': 'wifi', 'start_char': text.index('wifi'), 'end_char': text.index('wifi') + 4,
            'canonical_id': None, 'sentiment': 'negative'}
    response = client.post(BASE, json=body(draft, mentions=[battery, wifi]))
    assert response.status_code == 201, response.text
    assert response.json()['mentions'] == [battery, wifi]
    assert response.json()['original_predictions'][0]['raw_aspect'] == 'battery life'
    reopened = annotation(client, reference(before, text))
    assert reopened['status'] == 'reviewed' and reopened['mentions'] == [battery, wifi]
    assert client.get('/api/demo/products/demo-laptop').json() == before
    reopened_repository = Repository(str(app.state.repository.engine.url))
    try:
        with reopened_repository.transaction() as db:
            assert db.scalar(select(func.count()).select_from(ReviewAnnotation)) == 1
    finally:
        reopened_repository.engine.dispose()


def test_empty_review_requires_explicit_confirmation_to_complete(client):
    detail = saved(client)
    draft = annotation(client, reference(detail, 'Nothing to report.'))
    assert draft['mentions'] == []
    assert client.post(BASE, json=body(draft)).status_code == 422
    assert client.post(BASE, json=body(draft, confirmed_no_aspects=True)).status_code == 201
    assert client.get(BASE).json()['summary']['reviewed'] == 1


def test_status_filters_and_history_track_latest_revision(client):
    detail = saved(client)
    ref = reference(detail, 'Nothing to report.')
    first = annotation(client, ref)
    assert client.post(BASE, json=body(first, status='needs_review')).status_code == 201
    second = annotation(client, ref)
    assert client.post(BASE, json=body(second, status='needs_adjudication', reason='Need agreement about an implicit feature.')).status_code == 201
    assert client.get(BASE, params={'status': 'needs_adjudication'}).json()['items'][0]['review_id'] == ref['review_id']
    third = annotation(client, ref)
    assert client.post(BASE, json=body(third, confirmed_no_aspects=True)).status_code == 201
    assert client.get(BASE, params={'status': 'needs_adjudication'}).json()['items'] == []
    assert [row['status'] for row in annotation(client, ref)['history']] == ['reviewed', 'needs_adjudication', 'needs_review']
    assert client.get(BASE).json()['summary'] == {'total': 2, 'reviewed': 1, 'needs_review': 1, 'needs_adjudication': 0}


@pytest.mark.parametrize('defect', ['overlap', 'duplicate', 'wrong_text', 'outside', 'empty', 'canonical', 'missing_canonical', 'bool_offset', 'reviewer', 'reason', 'wrong_no_aspects'])
def test_invalid_annotation_is_rejected_without_partial_save(client, defect):
    detail = saved(client)
    draft = annotation(client, reference(detail, '😀 Great battery life; wifi is poor.'))
    request = body(draft)
    mention = request['mentions'][0]
    if defect in ('overlap', 'duplicate'):
        extra = deepcopy(mention)
        if defect == 'overlap':
            extra.update(raw_aspect='life', start_char=16, end_char=20)
        request['mentions'].append(extra)
    elif defect == 'wrong_text':
        mention['raw_aspect'] = 'wifi'
    elif defect == 'outside':
        mention['end_char'] = 999
    elif defect == 'empty':
        mention['end_char'] = mention['start_char']
    elif defect == 'canonical':
        mention['canonical_id'] = 'invented'
    elif defect == 'missing_canonical':
        del mention['canonical_id']
    elif defect == 'bool_offset':
        mention['start_char'] = True
    elif defect in ('reviewer', 'reason'):
        request[defect] = '  '
    else:
        request['confirmed_no_aspects'] = True
    assert client.post(BASE, json=request).status_code == 422
    assert annotation(client, reference(detail, '😀 Great battery life; wifi is poor.'))['history'] == []


def test_idempotent_retry_changed_payload_and_competing_annotation(client):
    detail = saved(client)
    draft = annotation(client, reference(detail, 'Nothing to report.'))
    request = body(draft, confirmed_no_aspects=True)
    response = client.post(BASE, json=request)
    assert client.post(BASE, json=request).json() == response.json()
    assert client.post(BASE, json={**request, 'reason': 'Changed'}).status_code == 409
    assert client.post(BASE, json=body(draft, confirmed_no_aspects=True)).status_code == 409
    assert len(annotation(client, reference(detail, 'Nothing to report.'))['history']) == 1


def test_later_aspect_correction_reopens_review_and_blocks_stale_annotation(client):
    detail = saved(client)
    ref = reference(detail, '😀 Great battery life; wifi is poor.')
    draft = annotation(client, ref)
    assert client.post(BASE, json=body(draft)).status_code == 201
    old = annotation(client, ref)
    mention = old['mentions'][0]
    decision = client.post('/api/demo/products/demo-laptop/corrections', json={**ref,
        'start_char': mention['start_char'], 'end_char': mention['end_char'], 'request_id': str(uuid4()),
        'decision': 'edited', 'reviewer': 'Reviewer B', 'reason': 'A different sentiment decision.',
        'canonical_id': 'battery', 'sentiment': 'negative'})
    assert decision.status_code == 201
    current = annotation(client, ref)
    assert current['status'] == 'needs_review' and current['corrections_changed']
    assert client.get(BASE).json()['summary']['reviewed'] == 0
    assert client.post(BASE, json=body(old)).status_code == 409
    assert client.post(BASE, json=body(current, reason='Rechecked the changed aspect decision.')).status_code == 201
    assert annotation(client, ref)['status'] == 'reviewed'


def test_existing_aspect_decisions_seed_initial_draft_but_do_not_complete_review(client):
    detail = saved(client)
    ref = reference(detail, '😀 Great battery life; wifi is poor.')
    tag = annotation(client, ref)['mentions'][0]
    response = client.post('/api/demo/products/demo-laptop/corrections', json={**ref,
        'start_char': tag['start_char'], 'end_char': tag['end_char'], 'request_id': str(uuid4()),
        'decision': 'edited', 'reviewer': 'Reviewer B', 'reason': 'Not an aspect.',
        'supported': False, 'canonical_id': None, 'sentiment': None})
    assert response.status_code == 201
    draft = annotation(client, ref)
    assert draft['mentions'] == [] and draft['status'] == 'needs_review'


def test_snapshot_changes_and_wrong_product_cannot_write_or_export(client):
    detail = saved(client)
    ref = reference(detail, 'Nothing to report.')
    draft = annotation(client, ref)
    other = client.post('/api/demo/products', json={'name': 'Other'}).json()['id']
    saved(client, ['Nothing to report.'], product=other)
    assert client.post(f'/api/demo/products/{other}/annotations', json=body(draft, confirmed_no_aspects=True)).status_code == 409
    saved(client, ['Great keyboard.'])
    assert client.post(BASE, json=body(draft, confirmed_no_aspects=True)).status_code == 409
    assert client.get(f'{BASE}/export', params={'snapshot_id': detail['snapshot_id']}).status_code == 409


def test_export_contains_latest_annotations_and_marks_outdated_completion(client):
    detail = saved(client)
    ref = reference(detail, 'Nothing to report.')
    draft = annotation(client, ref)
    client.post(BASE, json=body(draft, status='needs_review'))
    client.post(BASE, json=body(annotation(client, ref), confirmed_no_aspects=True))
    exported = client.get(f'{BASE}/export', params={'snapshot_id': detail['snapshot_id']}).json()
    assert len(exported['items']) == 1
    assert exported['items'][0]['status'] == 'reviewed'
    assert exported['items'][0]['review_text'] == 'Nothing to report.'
    assert exported['items'][0]['original_predictions'] == []
    assert not exported['items'][0]['applied_to_predictions']


def test_review_progress_survives_new_snapshot_with_same_analysis_and_cascades_on_clear(client):
    detail = saved(client)
    ref = reference(detail, 'Nothing to report.')
    client.post(BASE, json=body(annotation(client, ref), confirmed_no_aspects=True))
    saved(client, ['Great keyboard.'])
    assert client.get(BASE).json()['summary']['reviewed'] == 1
    assert client.delete('/api/demo/products/demo-laptop/saved-data').status_code == 200
    assert client.get(BASE).json()['summary']['total'] == 0
    with app.state.repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewAnnotation)) == 0


def test_export_does_not_mislabel_completion_after_a_new_correction(client):
    detail = saved(client, ['Great battery.'])
    ref = reference(detail, 'Great battery.')
    draft = annotation(client, ref)
    assert client.post(BASE, json=body(draft)).status_code == 201
    mention = draft['mentions'][0]
    assert client.post('/api/demo/products/demo-laptop/corrections', json={**ref,
        'start_char': mention['start_char'], 'end_char': mention['end_char'], 'request_id': str(uuid4()),
        'decision': 'edited', 'reviewer': 'Reviewer B', 'reason': 'New aspect decision.',
        'canonical_id': 'battery', 'sentiment': 'negative'}).status_code == 201
    result = client.get(f'{BASE}/export', params={'snapshot_id': detail['snapshot_id']}).json()['items'][0]
    assert result['status'] == 'reviewed'
    assert result['effective_status'] == 'needs_review' and result['corrections_changed']


def test_removing_one_import_preserves_other_reviews_annotation_history(client):
    batches = []
    for filename, text in [('one.txt', 'Great battery.'), ('two.txt', 'Nothing to report.')]:
        response = client.post('/api/demo/products/demo-laptop/imports', json={'filename': filename, 'content': text})
        assert response.status_code == 202
        batches.append(response.json()['id'])
    while app.state.worker.run_once():
        pass
    detail = client.get('/api/demo/products/demo-laptop').json()
    for text in ['Great battery.', 'Nothing to report.']:
        draft = annotation(client, reference(detail, text))
        assert client.post(BASE, json=body(draft, confirmed_no_aspects=not draft['mentions'])).status_code == 201
    assert client.delete(f'/api/demo/products/demo-laptop/imports/{batches[0]}').status_code == 200
    current = client.get('/api/demo/products/demo-laptop').json()
    assert client.get(BASE).json()['summary'] == {'total': 1, 'reviewed': 1, 'needs_review': 0, 'needs_adjudication': 0}
    surviving = annotation(client, reference(current, 'Nothing to report.'))
    assert surviving['history'][0]['snapshot_id'] == detail['snapshot_id']
    assert surviving['snapshot_id'] == current['snapshot_id'] != detail['snapshot_id']
    with app.state.repository.transaction() as db:
        assert db.scalar(select(func.count()).select_from(ReviewAnnotation)) == 1
