import pytest
from review_tag_generator.evidence_audit import audit_evidence


def report(positive, neutral, negative, contradictions=0):
    return audit_evidence({'aspects': [{
        'aspect_id': 'battery', 'aspect': 'Battery',
        'counts': {'positive': positive, 'neutral': neutral, 'negative': negative},
        'contradictory_review_count': contradictions,
    }]})['aspects'][0]


def test_minimum_support_is_fragile_even_with_unanimous_votes():
    result = report(3, 0, 0)
    assert result['fragile_tag']
    assert result['tag_stability'] == 0
    assert result['removal_scenarios'][0]['classification_after_removal'] == 'insufficient_evidence'


def test_classification_change_can_keep_the_same_tag():
    result = report(4, 1, 0)
    assert result['classification'] == 'excellent'
    assert result['classification_stability'] == pytest.approx(1 / 5)
    assert result['tag_stability'] == 1
    assert not result['fragile_tag']


def test_polarity_flip_is_counted_by_reviews_not_sentiment_categories():
    result = report(3, 0, 2)
    assert result['tag_stability'] == pytest.approx(2 / 5)
    assert result['opposing_review_votes']


def test_contradictory_neutral_is_separate_from_ordinary_neutral():
    result = report(1, 3, 1, contradictions=2)
    assert result['contradictory_review_count'] == 2
    assert result['ordinary_neutral_review_count'] == 1


def test_insufficient_support_is_not_a_fragile_published_tag():
    assert not report(2, 0, 0)['fragile_tag']
    assert audit_evidence({'aspects': []})['aspects'] == []
