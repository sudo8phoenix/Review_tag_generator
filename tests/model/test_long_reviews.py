import pytest
import torch
from types import SimpleNamespace

from review_tag_generator import ReviewAnalyzer
from review_tag_generator.transformer_models import ReviewTooLongError


@pytest.mark.model
def test_aspect_after_first_model_window_is_seen():
    analyzer = ReviewAnalyzer(use_transformer=True)
    text = "Nothing special here. " * 65 + "The battery is terrible."
    assert len(analyzer.models.aspect_tokenizer(text, add_special_tokens=False)["input_ids"]) > 256
    battery_token_id = analyzer.models.aspect_tokenizer("battery", add_special_tokens=False)["input_ids"][0]

    class KnownTokenModel:
        config = SimpleNamespace(id2label={0: "O", 1: "B-ASP", 2: "I-ASP"})

        def __call__(self, input_ids, **_):
            logits = torch.full((*input_ids.shape, 3), -10.0, device=input_ids.device)
            logits[:, :, 0] = 10.0
            matches = input_ids == battery_token_id
            logits[:, :, 0][matches] = -10.0
            logits[:, :, 1][matches] = 10.0
            return SimpleNamespace(logits=logits)

    analyzer.models.aspect_model = KnownTokenModel()
    predictions = analyzer.models.extract_aspects(text)
    assert any(item.aspect.lower() == "battery" and text[item.start_char:item.end_char] == item.aspect for item in predictions)


@pytest.mark.model
def test_over_budget_review_is_rejected():
    analyzer = ReviewAnalyzer(use_transformer=True)
    text = "laptop " * 4097
    with pytest.raises(ReviewTooLongError):
        analyzer.models.extract_aspects(text)
