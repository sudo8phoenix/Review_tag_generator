from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class Review:
    review_id: str
    product_id: str
    review_text: str
    product_category: str = "electronics"
    rating: float | None = None
    helpful_votes: int = 0


@dataclass(frozen=True)
class AspectPrediction:
    aspect: str
    start_char: int
    end_char: int
    confidence: float


@dataclass(frozen=True)
class SentimentPrediction:
    label: Sentiment
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class NormalizationResult:
    raw_aspect: str
    normalized_aspect: str | None
    similarity: float
    is_unknown: bool


@dataclass(frozen=True)
class TagResult:
    normalized_aspect: str | None
    sentiment: Sentiment
    tag: str | None
    confidence: float
    raw_aspect: str = ""
    start_char: int = 0
    end_char: int = 0


@dataclass
class ProductAggregate:
    product_id: str
    strengths: list[dict[str, Any]] = field(default_factory=list)
    weaknesses: list[dict[str, Any]] = field(default_factory=list)
    sentiment_distribution: dict[str, int] = field(default_factory=dict)
    aspect_frequencies: dict[str, int] = field(default_factory=dict)
    representative_reviews: list[dict[str, Any]] = field(default_factory=list)


def tag_result_from_mention(mention: Any) -> TagResult:
    """Project a validated API Mention onto the existing core TagResult shape.

    This is intentionally lossy: callers needing probabilities, context and
    normalization metadata must use the HTTP Mention itself. The core package
    stays independent of Pydantic and existing positional constructors remain
    unchanged.
    """
    return TagResult(
        normalized_aspect=mention.normalized_aspect,
        sentiment=Sentiment(mention.sentiment),
        tag=mention.tag or "",
        confidence=mention.confidence,
        raw_aspect=mention.raw_aspect,
        start_char=mention.start_char,
        end_char=mention.end_char,
    )
