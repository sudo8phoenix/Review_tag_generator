from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from .aggregation import aggregate
from .extraction import extract_aspects
from .normalization import AspectNormalizer
from .schemas import Review, TagResult
from .sentiment import predict_sentiment, aspect_context_span
from .tags import generate_tag
from .artifacts import verify_checkpoint


class ReviewAnalyzer:
    def __init__(
        self,
        use_transformer: bool | str = "auto",
        aspect_model_path: str | None = None,
        sentiment_model_path: str | None = None,
        device: str = "cpu",
        context_policy: str = "full_review",
        *,
        semantic_model_path: str | None = None,
        semantic_revision: str | None = None,
        normalization_threshold: float | None = None,
        normalizer: AspectNormalizer | None = None,
    ):
        default_root = Path(__file__).resolve().parents[2]
        aspect_path = Path(aspect_model_path or default_root / "models/aspect_extractor/distilbert_weighted_lr3e5/best")
        sentiment_path = Path(sentiment_model_path or default_root / "models/sentiment_classifier/distilbert/best")
        if use_transformer not in (True, False, "auto"):
            raise ValueError("use_transformer must be True, False, or 'auto'")
        if normalizer is not None and any(value is not None for value in (semantic_model_path, semantic_revision, normalization_threshold)):
            raise ValueError("provide a normalizer or semantic configuration, not both")
        self.normalizer = normalizer or AspectNormalizer(
            semantic_model_path=semantic_model_path,
            semantic_revision=semantic_revision,
            threshold=normalization_threshold,
        )
        self.context_policy = context_policy if use_transformer is not False else "local_clause"
        self.models = None
        self.backend = "heuristic" if use_transformer is False else "transformer"
        if use_transformer is not False:
            verify_checkpoint(aspect_path, default_root / "audit/evidence/A2/aspect_training_manifest.json", "aspect")
            verify_checkpoint(sentiment_path, default_root / "audit/evidence/A3/sentiment_training_manifest.json", "sentiment")
            from .transformer_models import TransformerModels
            self.models = TransformerModels(aspect_path, sentiment_path, device=device, context_policy=context_policy)

    def analyze_review(self, review: Review) -> list[TagResult]:
        results = []
        aspects = self.models.extract_aspects(review.review_text) if self.models else extract_aspects(review.review_text)
        for aspect in aspects:
            normalized = self.normalizer.normalize(aspect.aspect, context=review.review_text)
            sentiment = self.models.predict_sentiment(review.review_text, aspect.aspect, aspect.start_char, aspect.end_char) if self.models else predict_sentiment(review.review_text, aspect.aspect, aspect.start_char, aspect.end_char)
            _, context_start, context_end = self.models.select_sentiment_context(review.review_text, aspect.aspect, aspect.start_char, aspect.end_char) if self.models else aspect_context_span(review.review_text, aspect.start_char, aspect.end_char)
            results.append(TagResult(normalized.normalized_aspect, sentiment.label, generate_tag(normalized.normalized_aspect, sentiment.label), min(aspect.confidence, sentiment.confidence), aspect.aspect, aspect.start_char, aspect.end_char,
                normalized_aspect_id=normalized.normalized_aspect_id,
                normalization_method=normalized.method, normalization_similarity=normalized.similarity,
                aspect_confidence=aspect.confidence, sentiment_confidence=sentiment.confidence,
                probabilities=sentiment.probabilities, context_start_char=context_start, context_end_char=context_end))
        return results

    def analyze(self, review: Review) -> dict:
        tags = self.analyze_review(review)
        return {"review": asdict(review), "tags": [asdict(t) for t in tags], "backend": self.backend, "context_policy": self.context_policy}

    def aggregate(self, reviews: list[Review]):
        grouped = {}
        for review in reviews:
            grouped.setdefault(review.product_id, []).append((review, self.analyze_review(review)))
        return {product: asdict(aggregate(product, rows)) for product, rows in grouped.items()}
