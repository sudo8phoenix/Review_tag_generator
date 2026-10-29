from copy import deepcopy

import pytest

from backend.app.llm_annotation import annotate_fallback
from review_tag_generator import ReviewAnalyzer
from review_tag_generator.schemas import Review

STATUS = {'enabled': True, 'provider': 'ollama', 'model': 'test-model'}


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('LLM_AUTO_ANNOTATE', '1')


def result(text='😀 The battery is great.'):
    return ReviewAnalyzer(use_transformer=False).analyze(Review('review', 'product', text))


def mention(text, aspect='battery', canonical='battery'):
    start = text.index(aspect)
    return {'raw_aspect': aspect, 'start_char': start, 'end_char': start + len(aspect),
            'canonical_id': canonical, 'sentiment': 'positive'}


def test_no_aspects_extracts_grounded_mentions_and_preserves_originals():
    original = result()
    original['tags'] = []
    before = deepcopy(original)
    output = annotate_fallback(original, lambda *_: {'mentions': [mention(original['review']['review_text'])]}, STATUS)
    assert original == before
    assert output['tags'][0]['normalized_aspect_id'] == 'battery'
    assert output['tags'][0]['start_char'] == 6
    assert output['tags'][0]['confidence'] == 0.5
    assert output['model_predictions'] == []
    assert output['llm_annotation']['status'] == 'applied'
    assert output['llm_annotation']['human_verified'] is False


def test_only_uncertain_tags_are_replaced():
    original = result('The battery is great; display is bright.')
    original['tags'][0]['confidence'] = 0.3
    original['tags'][1]['confidence'] = 0.95
    seen = {}

    def generate(system, payload, schema):
        seen.update(payload)
        assert 'untrusted data' in system
        return {'mentions': [mention(payload['review_text'])]}

    output = annotate_fallback(original, generate, STATUS)
    assert len(seen['target_spans']) == 1
    assert output['tags'][1] == original['tags'][1]
    assert output['tags'][0]['normalization_method'] == 'llm'


@pytest.mark.parametrize('change', [
    {'raw_aspect': 'invented'}, {'end_char': 999}, {'canonical_id': 'invented'},
    {'start_char': True}, {'sentiment': 'mixed'}, {'start_char': 0, 'end_char': 1, 'raw_aspect': '😀'},
])
def test_invalid_or_unrequested_mentions_keep_entire_original(change):
    original = result()
    original['tags'][0]['confidence'] = 0.1
    bad = {**mention(original['review']['review_text']), **change}
    output = annotate_fallback(original, lambda *_: {'mentions': [bad]}, STATUS)
    assert output['tags'] == original['tags']
    assert output['llm_annotation']['status'] == 'failed'


def test_unknown_aspect_stays_unknown_and_empty_response_abstains():
    original = result('The hinge is sturdy.')
    original['tags'] = []
    output = annotate_fallback(original, lambda *_: {'mentions': [mention(original['review']['review_text'], 'hinge', None)]}, STATUS)
    assert output['tags'][0]['normalized_aspect_id'] is None
    assert output['tags'][0]['tag'] is None
    abstained = annotate_fallback(original, lambda *_: {'mentions': []}, STATUS)
    assert abstained['tags'] == []
    assert abstained['llm_annotation']['status'] == 'abstained'


def test_outage_does_not_fail_model_analysis():
    original = result()
    original['tags'] = []

    def generate(*_):
        raise TimeoutError('private provider response')

    output = annotate_fallback(original, generate, STATUS)
    assert output['tags'] == []
    assert output['llm_annotation']['status'] == 'failed'
    assert 'private' not in str(output)


def test_confident_or_disabled_analysis_never_calls_provider(monkeypatch):
    def forbidden(*_):
        pytest.fail('Provider must not be called')

    original = result()
    original['tags'][0]['confidence'] = 0.9
    assert annotate_fallback(original, forbidden, STATUS) is original
    original['tags'] = []
    assert annotate_fallback(original, forbidden, {'enabled': False}) is original
    monkeypatch.setenv('LLM_AUTO_ANNOTATE', '0')
    assert annotate_fallback(original, forbidden, STATUS) is original


def test_duplicate_spans_reject_whole_response():
    original = result()
    original['tags'] = []
    item = mention(original['review']['review_text'])
    output = annotate_fallback(original, lambda *_: {'mentions': [item, item]}, STATUS)
    assert output['tags'] == []
    assert output['llm_annotation']['status'] == 'failed'


def test_miscounted_offsets_are_resolved_only_for_exact_unique_source_phrases():
    original = result()
    original['tags'] = []
    text = original['review']['review_text']
    item = {**mention(text), 'start_char': 5, 'end_char': 12}
    output = annotate_fallback(original, lambda *_: {'mentions': [item]}, STATUS)
    assert output['llm_annotation']['status'] == 'applied'
    assert output['tags'][0]['start_char'] == text.index('battery')
    assert output['tags'][0]['end_char'] == text.index('battery') + 7
    assert output['llm_annotation']['resolved_offsets']


def test_miscounted_offsets_cannot_guess_between_repeated_phrases():
    original = result('battery is good; battery is bad.')
    original['tags'] = []
    item = {**mention(original['review']['review_text']), 'start_char': 1, 'end_char': 8}
    output = annotate_fallback(original, lambda *_: {'mentions': [item]}, STATUS)
    assert output['tags'] == []
    assert output['llm_annotation']['status'] == 'failed'


def test_live_gonka_sample_with_miscounted_offsets_is_grounded():
    text = 'The screen is sharp, but the battery dies in two hours. The hinge feels solid.'
    original = result(text)
    original['tags'] = []
    # Recorded synthetic MiniMax response: labels were correct, offsets were not.
    mentions = [
        {'raw_aspect': 'screen', 'start_char': 4, 'end_char': 10, 'canonical_id': 'display', 'sentiment': 'positive'},
        {'raw_aspect': 'battery', 'start_char': 29, 'end_char': 35, 'canonical_id': 'battery', 'sentiment': 'negative'},
        {'raw_aspect': 'hinge', 'start_char': 60, 'end_char': 64, 'canonical_id': 'build_quality', 'sentiment': 'positive'},
    ]
    output = annotate_fallback(original, lambda *_: {'mentions': mentions}, STATUS)
    assert output['llm_annotation']['status'] == 'applied'
    assert len(output['tags']) == 3
    for tag in output['tags']:
        assert text[tag['start_char']:tag['end_char']] == tag['raw_aspect']
