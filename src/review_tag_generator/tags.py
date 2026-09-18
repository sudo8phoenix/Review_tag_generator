from __future__ import annotations

from .schemas import Sentiment

_ADJECTIVES = {Sentiment.POSITIVE: "Great", Sentiment.NEUTRAL: "Mixed", Sentiment.NEGATIVE: "Poor"}


def generate_tag(normalized_aspect: str | None, sentiment: Sentiment) -> str:
    if not normalized_aspect:
        return "Uncategorized Feedback"
    return f"{_ADJECTIVES[sentiment]} {normalized_aspect}"
