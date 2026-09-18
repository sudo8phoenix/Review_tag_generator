from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from .aggregation import aggregate
from .extraction import extract_aspects
from .ontology import normalize_aspect
from .schemas import Review, TagResult
from .sentiment import predict_sentiment
from .tags import generate_tag


class ReviewAnalyzer:
    def __init__(self, use_transformer: bool | str = "auto", aspect_model_path: str | None = None, sentiment_model_path: str | None = None):
        default_root = Path(__file__).resolve().parents[2]
        aspect_path = Path(aspect_model_path or default_root / "models/aspect_extractor/distilbert_weighted_lr3e5/best")
        sentiment_path = Path(sentiment_model_path or default_root / "models/sentiment_classifier/distilbert/best")
        self.models = None
        if use_transformer is not False and aspect_path.exists() and sentiment_path.exists():
            try:
                from .transformer_models import TransformerModels
                self.models = TransformerModels(aspect_path, sentiment_path)
            except (ImportError, RuntimeError):
                if use_transformer is True:
                    raise

    def analyze_review(self, review: Review) -> list[TagResult]:
        results = []
        aspects = self.models.extract_aspects(review.review_text) if self.models else extract_aspects(review.review_text)
        for aspect in aspects:
            normalized = normalize_aspect(aspect.aspect)
            sentiment = self.models.predict_sentiment(review.review_text, aspect.aspect, aspect.start_char, aspect.end_char) if self.models else predict_sentiment(review.review_text, aspect.aspect, aspect.start_char, aspect.end_char)
            results.append(TagResult(normalized.normalized_aspect, sentiment.label, generate_tag(normalized.normalized_aspect, sentiment.label), min(aspect.confidence, sentiment.confidence), aspect.aspect, aspect.start_char, aspect.end_char))
        return results

    def analyze(self, review: Review) -> dict:
        tags = self.analyze_review(review)
        return {"review": asdict(review), "tags": [asdict(t) for t in tags]}

    def aggregate(self, reviews: list[Review]):
        grouped = {}
        for review in reviews:
            grouped.setdefault(review.product_id, []).append((review, self.analyze_review(review)))
        return {product: asdict(aggregate(product, rows)) for product, rows in grouped.items()}
