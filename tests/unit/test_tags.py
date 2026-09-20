import pytest

from review_tag_generator.normalization import get_ontology
from review_tag_generator.schemas import Sentiment
from review_tag_generator.tags import generate_tag


@pytest.mark.parametrize("sentiment", list(Sentiment))
@pytest.mark.parametrize("aspect", get_ontology().aspects, ids=lambda aspect: aspect.id)
def test_every_ontology_aspect_has_deterministic_tag_for_every_sentiment(aspect, sentiment):
    first = generate_tag(aspect.id, sentiment)
    assert first
    assert generate_tag(aspect.id, sentiment) == first
    assert generate_tag(aspect.display_label, sentiment) == first
    assert "Mixed" not in first


@pytest.mark.parametrize(
    ("aspect", "sentiment", "expected"),
    [
        ("display", Sentiment.POSITIVE, "Great Display"),
        ("battery", Sentiment.NEGATIVE, "Poor Battery"),
        ("display", Sentiment.NEUTRAL, "Neutral Display Feedback"),
        ("weight", Sentiment.POSITIVE, "Low Weight"),
        ("weight", Sentiment.NEGATIVE, "Heavy Build"),
        ("heating", Sentiment.POSITIVE, "Runs Cool"),
        ("heating", Sentiment.NEGATIVE, "Overheats"),
        ("value", Sentiment.POSITIVE, "Good Value"),
        ("value", Sentiment.NEGATIVE, "Poor Value"),
        ("price", Sentiment.POSITIVE, "Affordable Price"),
        ("price", Sentiment.NEGATIVE, "High Price"),
    ],
)
def test_required_and_aspect_specific_wording(aspect, sentiment, expected):
    assert generate_tag(aspect, sentiment) == expected


@pytest.mark.parametrize("aspect", [None, "", "hinge", "unrecognized aspect"])
def test_unknown_aspects_return_no_tag(aspect):
    assert generate_tag(aspect, Sentiment.POSITIVE) is None


def test_invalid_sentiment_and_canonical_id_are_rejected():
    with pytest.raises(ValueError, match="invalid sentiment"):
        generate_tag("display", "mixed")
    with pytest.raises(ValueError, match="unknown canonical aspect ID"):
        generate_tag("unknown_feature", Sentiment.POSITIVE)


def test_legacy_display_label_input_remains_supported():
    assert generate_tag("Display", "positive") == "Great Display"
