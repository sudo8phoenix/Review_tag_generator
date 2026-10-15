from review_tag_generator import Review, ReviewAnalyzer
from review_tag_generator.ontology import normalize_aspect
from review_tag_generator.normalization import AspectNormalizer, build_ontology
from review_tag_generator.schemas import AspectPrediction, SentimentPrediction, Sentiment
import review_tag_generator.pipeline as pipeline


def test_requested_review_end_to_end():
    review = Review("r1", "p1", "Amazing display but terrible battery.")
    result = ReviewAnalyzer(use_transformer=False).analyze(review)
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
    analyzer = ReviewAnalyzer(use_transformer=False)
    reviews = [Review("r1", "p1", "Amazing display but terrible battery."), Review("r2", "p1", "Good screen and good battery.")]
    product = analyzer.aggregate(reviews)["p1"]
    assert product["aspect_frequencies"] == {"Display": 2, "Battery": 2}
    assert product["sentiment_distribution"] == {"positive": 3, "negative": 1}
    assert product["strengths"][0]["aspect"] in {"Battery", "Display"}


def test_analyzer_uses_explicit_semantic_normalizer_with_review_context(monkeypatch):
    ontology = build_ontology({"version": "test-v1", "aspects": [
        {"id": "battery", "label": "Battery", "aliases": ["battery life"]},
        {"id": "charging", "label": "Charging", "aliases": ["charging"]},
    ]})
    vectors = {
        "battery": [1, 0], "battery life": [1, 0], "charging": [0, 1],
        "aspect mention charge review context the charging port is fast": [0, 1],
    }
    normalizer = AspectNormalizer(ontology=ontology, threshold=0.9,
                                  encoder=lambda texts: [vectors.get(text, [1, 0]) for text in texts])
    monkeypatch.setattr(pipeline, "extract_aspects", lambda _: [AspectPrediction("charge", 4, 10, 0.9)])
    monkeypatch.setattr(pipeline, "predict_sentiment", lambda *args: SentimentPrediction(
        Sentiment.POSITIVE, 0.9, {"positive": 0.9, "neutral": 0.05, "negative": 0.05}))
    analyzer = ReviewAnalyzer(use_transformer=False, normalizer=normalizer)
    result = analyzer.analyze(Review("r1", "p1", "The charging port is fast."))
    assert result["tags"][0]["normalized_aspect"] == "Charging"
    assert result["tags"][0]["tag"] == "Great Charging"
