from dataclasses import asdict
from itertools import permutations
import math

import pytest

from review_tag_generator.aggregation import SavedReviewAnalysis, aggregate_saved_analyses
from review_tag_generator.schemas import Review, Sentiment, TagResult


def mention(aspect, sentiment, confidence=0.9, *, raw="battery", start=0, tag=None):
    return TagResult(
        normalized_aspect=aspect,
        sentiment=Sentiment(sentiment),
        tag=tag or f"{sentiment} {aspect}",
        confidence=confidence,
        raw_aspect=raw,
        start_char=start,
        end_char=start + len(raw),
    )


def row(review_id, mentions=(), *, text=None, helpful=0):
    return SavedReviewAnalysis(
        Review(review_id, "p1", text or f"review {review_id}", helpful_votes=helpful),
        tuple(mentions),
    )


def aspect(snapshot, identifier):
    return next(item for item in snapshot.aspects if item["aspect_id"] == identifier)


def test_empty_product_has_explicit_zero_distribution_and_no_nan():
    result = aggregate_saved_analyses("p1", [])
    assert result.review_count == 0
    assert result.sentiment_distribution == {"positive": 0, "neutral": 0, "negative": 0}
    assert result.aspects == []
    assert result.top_tags == []
    assert result.representative_reviews == []
    assert all(math.isfinite(value) for value in result.sentiment_distribution.values())


def test_alias_mentions_and_duplicate_analysis_make_one_review_vote():
    saved = row("r1", [
        mention("Battery", "positive", 0.95, raw="battery"),
        mention("battery", "positive", 0.72, raw="battery life", start=20),
    ])
    result = aggregate_saved_analyses("p1", [saved, saved])
    battery = aspect(result, "battery")
    assert battery["mention_count"] == 2
    assert battery["review_count"] == 1
    assert battery["counts"] == {"positive": 1, "neutral": 0, "negative": 0}
    assert battery["average_confidence"] == 0.72
    assert battery["classification"] == "insufficient_evidence"
    assert result.sentiment_distribution == {"positive": 1, "neutral": 0, "negative": 0}


def test_contradictory_review_votes_neutral_and_is_explicitly_mixed_evidence():
    rows = [
        row("r1", [mention("battery", "positive", 0.9), mention("battery", "negative", 0.7, raw="battery", start=10)]),
        row("r2", [mention("battery", "neutral", 0.8)]),
        row("r3", [mention("battery", "neutral", 0.6)]),
    ]
    result = aggregate_saved_analyses("p1", rows)
    battery = aspect(result, "battery")
    assert battery["mention_count"] == 4
    assert battery["review_count"] == 3
    assert battery["contradictory_review_count"] == 1
    assert battery["counts"] == {"positive": 0, "neutral": 3, "negative": 0}
    assert battery["classification"] == "neutral"
    representative = next(
        item for item in result.representative_reviews
        if item["review_id"] == "r1" and item["sentiment"] == "neutral"
    )
    assert representative["evidence_type"] == "mixed_within_review"
    assert {item["sentiment"] for item in representative["mentions"]} == {"positive", "negative"}


def test_two_reviews_are_insufficient_and_excluded_from_ranked_tags():
    rows = [row("r1", [mention("display", "positive")]), row("r2", [mention("display", "positive")])]
    result = aggregate_saved_analyses("p1", rows)
    display = aspect(result, "display")
    assert display["classification"] == "insufficient_evidence"
    assert display["rank"] is None
    assert display["aggregate_tag"] is None
    assert "display" in result.insufficient_evidence
    assert result.top_tags == []


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        (["positive", "positive", "positive", "positive", "negative"], "excellent"),
        (["positive", "positive", "positive", "neutral", "neutral"], "good"),
        (["negative", "negative", "negative", "negative", "positive"], "poor"),
        (["negative", "negative", "negative", "neutral", "neutral"], "weak"),
        (["positive", "positive", "negative", "negative", "neutral"], "mixed"),
    ],
)
def test_classification_boundaries_and_mixed_partition(labels, expected):
    rows = [row(f"r{i}", [mention("performance", label)]) for i, label in enumerate(labels)]
    result = aggregate_saved_analyses("p1", rows)
    item = aspect(result, "performance")
    assert item["classification"] == expected
    if expected in {"excellent", "good"}:
        assert "performance" in result.strengths
        assert "performance" not in result.weaknesses
    elif expected in {"poor", "weak"}:
        assert "performance" in result.weaknesses
        assert "performance" not in result.strengths
    elif expected == "mixed":
        assert "performance" in result.mixed
        assert "performance" not in result.strengths + result.weaknesses
        assert item["aggregate_tag"] == "Mixed Performance Feedback"
    if expected in {"excellent", "good"}:
        assert item["aggregate_tag"] == "Great Performance"
    elif expected in {"poor", "weak"}:
        assert item["aggregate_tag"] == "Poor Performance"


def test_neutral_classification_uses_m06_neutral_template():
    result = aggregate_saved_analyses("p1", [
        row(f"n{i}", [mention("display", "neutral")]) for i in range(3)
    ])
    assert aspect(result, "display")["classification"] == "neutral"
    assert aspect(result, "display")["aggregate_tag"] == "Neutral Display Feedback"


def test_ratios_score_tie_breaking_and_rank_are_unrounded_and_stable():
    rows = [
        row("a", [mention("battery", "positive", 0.8)]),
        row("b", [mention("battery", "positive", 0.8)]),
        row("c", [mention("battery", "positive", 0.8)]),
        row("d", [mention("display", "positive", 0.8)]),
        row("e", [mention("display", "positive", 0.8)]),
        row("f", [mention("display", "positive", 0.8)]),
    ]
    snapshots = [aggregate_saved_analyses("p1", order) for order in permutations(rows)]
    assert all(asdict(item) == asdict(snapshots[0]) for item in snapshots[1:])
    assert [item["aspect_id"] for item in snapshots[0].aspects] == ["battery", "display"]
    battery = aspect(snapshots[0], "battery")
    assert battery["ratios"] == {"positive": 1.0, "neutral": 0.0, "negative": 0.0}
    assert battery["score"] == pytest.approx(math.log1p(3) * 0.8)
    assert battery["rank"] == 1
    assert snapshots[0].top_tags[0]["rank"] == 1


def test_representatives_are_distinct_ranked_reviews_and_only_supporting_mentions():
    rows = [
        row("r3", [mention("display", "positive", 0.8)], helpful=99),
        row("r2", [mention("display", "positive", 0.9)], helpful=0),
        row("r1", [mention("display", "positive", 0.9)], helpful=1),
        row("r4", [mention("display", "negative", 0.99)], helpful=100),
    ]
    result = aggregate_saved_analyses("p1", rows, representative_limit=2)
    positive = [
        item for item in result.representative_reviews
        if item["aspect_id"] == "display" and item["sentiment"] == "positive"
    ]
    assert [item["review_id"] for item in positive] == ["r1", "r2"]
    assert len({item["review_id"] for item in positive}) == 2
    assert all(m["sentiment"] == "positive" for rep in positive for m in rep["mentions"])


def test_unknown_aspects_are_not_added_to_product_counts_and_rows_are_validated():
    result = aggregate_saved_analyses("p1", [row("r1", [mention(None, "positive", raw="hinge")])])
    assert result.review_count == 1
    assert result.aspects == []
    with pytest.raises(ValueError, match="different product"):
        aggregate_saved_analyses("p1", [SavedReviewAnalysis(Review("r2", "p2", "text"), ())])
    with pytest.raises(ValueError, match="conflicting saved analyses"):
        aggregate_saved_analyses("p1", [row("dup", [mention("battery", "positive")]), row("dup", [mention("battery", "negative")])])
