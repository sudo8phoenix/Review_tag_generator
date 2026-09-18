from __future__ import annotations

from pathlib import Path

from .schemas import AspectPrediction, Sentiment, SentimentPrediction
from .sentiment import aspect_context


class TransformerModels:
    """Thin inference wrapper around the two trained DistilBERT checkpoints."""

    def __init__(self, aspect_path: str | Path, sentiment_path: str | Path, max_length: int = 256):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the optional transformer dependencies to load the trained models") from exc

        self.torch = torch
        self.max_length = max_length
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.aspect_tokenizer = AutoTokenizer.from_pretrained(str(aspect_path), use_fast=True)
        self.aspect_model = AutoModelForTokenClassification.from_pretrained(str(aspect_path)).to(self.device).eval()
        self.sentiment_tokenizer = AutoTokenizer.from_pretrained(str(sentiment_path), use_fast=True)
        self.sentiment_model = AutoModelForSequenceClassification.from_pretrained(str(sentiment_path)).to(self.device).eval()

    def extract_aspects(self, text: str) -> list[AspectPrediction]:
        encoded = self.aspect_tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=self.max_length, return_tensors="pt")
        offsets = encoded.pop("offset_mapping")[0].tolist()
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            probabilities = self.torch.softmax(self.aspect_model(**encoded).logits[0], dim=-1).cpu()
        predictions = []
        current = None
        for (start, end), probs in zip(offsets, probabilities):
            if start == end:
                continue
            label_id = int(probs.argmax())
            label = self.aspect_model.config.id2label.get(label_id, str(label_id))
            confidence = float(probs[label_id])
            if label == "B-ASP":
                if current:
                    predictions.append(current)
                current = [start, end, [confidence]]
            elif label == "I-ASP" and current:
                current[1] = end
                current[2].append(confidence)
            elif current:
                predictions.append(current)
                current = None
        if current:
            predictions.append(current)
        return [
            AspectPrediction(text[start:end], start, end, round(sum(scores) / len(scores), 4))
            for start, end, scores in predictions
            if text[start:end].strip()
        ]

    def predict_sentiment(self, review: str, aspect: str, start_char: int | None = None, end_char: int | None = None) -> SentimentPrediction:
        context = aspect_context(review, start_char, end_char) if start_char is not None and end_char is not None else review
        encoded = self.sentiment_tokenizer(context, aspect, truncation="only_first", max_length=self.max_length, return_tensors="pt")
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            probabilities = self.torch.softmax(self.sentiment_model(**encoded).logits[0], dim=-1).cpu()
        label_id = int(probabilities.argmax())
        label_name = self.sentiment_model.config.id2label[label_id].lower()
        label = Sentiment(label_name)
        return SentimentPrediction(label, round(float(probabilities[label_id]), 4), {
            self.sentiment_model.config.id2label[i].lower(): round(float(probabilities[i]), 4)
            for i in range(len(probabilities))
        })
