from types import SimpleNamespace

import scripts.evaluate_pipeline as evaluator


class FakeModels:
    def __init__(self):
        self.context_policy = None

    def extract_aspects(self, _text):
        return [SimpleNamespace(start_char=0, end_char=4, aspect="good")]

    def predict_sentiment(self, *_args):
        return SimpleNamespace(label=SimpleNamespace(value="negative"),
                               probabilities={"negative": 0.8, "neutral": 0.1, "positive": 0.1})


def test_complete_error_export_records_mismatched_spans_and_sentiment_without_review_text():
    models = FakeModels()
    reviews = [{"review_id": "r1", "review_text": "good screen",
                "annotations": [{"start_char": 0, "end_char": 4, "aspect": "good"},
                                {"start_char": 5, "end_char": 11, "aspect": "screen"}]}]
    pairs = [{"review_id": "r1", "review_text": "good screen", "aspect_text": "screen",
              "start_char": 5, "end_char": 11, "label": "positive"}]
    aspects, sentiments = evaluator.collect_error_exports(models, reviews, pairs, "full_review")
    assert len(aspects) == len(sentiments) == 1
    assert aspects[0]["error_types"] == ["false_negative"]
    assert aspects[0]["gold_spans"][-1]["aspect"] == "screen"
    assert sentiments[0]["gold"] == "positive"
    assert sentiments[0]["predicted"] == "negative"
    assert "review_text" not in aspects[0] and "review_text" not in sentiments[0]
    assert models.context_policy == "full_review"
