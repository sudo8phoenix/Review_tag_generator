import pytest

from review_tag_generator.sentiment import aspect_context_span, predict_sentiment


def test_repeated_identical_clause_uses_second_occurrence():
    text = "Amazing display but terrible battery. Amazing display but terrible battery."
    start = text.rindex("battery")
    context, context_start, context_end = aspect_context_span(text, start, start + 7)
    assert context == "terrible battery"
    assert context_start > text.index("terrible battery")
    assert text[context_start:context_end] == context


def test_context_preserves_negation_and_contrast():
    text = "The display is not good, but the battery is not bad."
    screen = text.index("display")
    battery = text.index("battery")
    assert predict_sentiment(text, "display", screen, screen + 7).label.value == "negative"
    assert predict_sentiment(text, "battery", battery, battery + 7).label.value == "positive"


def test_full_review_policy_preserves_original():
    text = "Amazing display but terrible battery."
    assert aspect_context_span(text, 8, 15, "full_review") == (text, 0, len(text))


def test_invalid_context_offsets_fail():
    with pytest.raises(ValueError):
        aspect_context_span("battery", 6, 50)


def test_honorific_does_not_cut_a_clause():
    text = "Dr. Lee says the display is excellent, but the battery is weak."
    start = text.index("display")
    assert aspect_context_span(text, start, start + 7)[0] == "Dr. Lee says the display is excellent,"
