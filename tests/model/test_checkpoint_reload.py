import pytest

from review_tag_generator import Review, ReviewAnalyzer


@pytest.mark.model
def test_real_checkpoints_reload_and_predict():
    review = Review("checkpoint-smoke", "demo", "Amazing display but terrible battery.")
    first = ReviewAnalyzer(use_transformer=True)
    second = ReviewAnalyzer(use_transformer=True)
    left, right = first.analyze(review), second.analyze(review)
    assert left == right
    assert left["backend"] == "transformer"
    assert [(tag["normalized_aspect"], review.review_text[tag["start_char"]:tag["end_char"]])
            for tag in left["tags"]] == [("Display", "display"), ("Battery", "battery")]
    assert all(0 <= tag["confidence"] <= 1 for tag in left["tags"])
