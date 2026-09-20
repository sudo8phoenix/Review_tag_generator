import pytest

from review_tag_generator import ReviewAnalyzer


@pytest.mark.model
def test_real_model_contrast_and_reverse_contrast():
    model = ReviewAnalyzer(use_transformer=True).models
    for text, expected in [
        ("Amazing display but terrible battery.", ("positive", "negative")),
        ("Terrible display but amazing battery.", ("negative", "positive")),
    ]:
        display = text.index("display")
        battery = text.index("battery")
        actual = (
            model.predict_sentiment(text, "display", display, display + 7),
            model.predict_sentiment(text, "battery", battery, battery + 7),
        )
        assert tuple(result.label.value for result in actual) == expected
        assert all(abs(sum(result.probabilities.values()) - 1) < 1e-5 for result in actual)


@pytest.mark.model
def test_long_full_review_keeps_aspect_in_sentiment_window():
    model = ReviewAnalyzer(use_transformer=True, context_policy="full_review").models
    text = "A plain laptop. " * 80 + "The battery is terrible."
    start = text.index("battery")
    context, context_start, context_end = model.select_sentiment_context(text, "battery", start, start + 7)
    assert context_start <= start < start + 7 <= context_end
    assert context == text[context_start:context_end]
    assert len(model.sentiment_tokenizer(context, "battery", add_special_tokens=True)["input_ids"]) <= 256
