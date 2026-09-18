import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from review_tag_generator import Review, ReviewAnalyzer
from review_tag_generator.ontology import normalize_aspect


def test_requested_review_end_to_end():
    review = Review("r1", "p1", "Amazing display but terrible battery.")
    result = ReviewAnalyzer().analyze(review)
    assert [(x["normalized_aspect"], x["sentiment"], x["tag"]) for x in result["tags"]] == [
        ("Display", "positive", "Great Display"),
        ("Battery", "negative", "Poor Battery"),
    ]
    assert [review.review_text[t["start_char"]:t["end_char"]] for t in result["tags"]] == ["display", "battery"]


def test_normalization_aliases_and_unknowns():
    assert normalize_aspect("screen").normalized_aspect == "Display"
    assert normalize_aspect("battery life").normalized_aspect == "Battery"
    assert normalize_aspect("hinge").is_unknown


def test_product_aggregation():
    analyzer = ReviewAnalyzer()
    reviews = [Review("r1", "p1", "Amazing display but terrible battery."), Review("r2", "p1", "Good screen and good battery.")]
    product = analyzer.aggregate(reviews)["p1"]
    assert product["aspect_frequencies"] == {"Display": 2, "Battery": 2}
    assert product["sentiment_distribution"] == {"positive": 3, "negative": 1}
    assert product["strengths"][0]["aspect"] in {"Battery", "Display"}
