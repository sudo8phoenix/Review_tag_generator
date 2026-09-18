from __future__ import annotations

import re
from .schemas import Sentiment, SentimentPrediction

POSITIVE = {"amazing", "excellent", "great", "good", "love", "loved", "gorgeous", "sharp", "fast", "reliable", "wonderful"}
NEGATIVE = {"terrible", "bad", "poor", "hate", "hated", "awful", "slow", "weak", "worse", "broken", "barely", "disappointing"}
NEGATIONS = {"not", "never", "no", "isn't", "isnt", "wasn't", "wasnt", "hardly", "barely"}


def aspect_context(review: str, start_char: int, end_char: int) -> str:
    """Return the clause containing an aspect to reduce sentiment leakage across aspects."""
    clauses = re.split(r"\b(?:but|however|although|while)\b|[.!?]", review, flags=re.I)
    for clause in clauses:
        offset = review.find(clause)
        if offset <= start_char < offset + len(clause):
            return clause.strip()
    return review


def predict_sentiment(review: str, aspect: str, start_char: int | None = None, end_char: int | None = None):
    if start_char is not None and end_char is not None:
        left = review[max(0, start_char - 70):start_char]
        right = review[end_char:end_char + 70]
        window = left + " " + right
    else:
        window = review
    # Keep conjunction-separated clauses local so "amazing display but terrible battery"
    # does not mix the praise for one aspect with the criticism of another.
    if start_char is not None and end_char is not None:
        window = aspect_context(review, start_char, end_char)
    tokens = re.findall(r"[a-z]+(?:n't)?", window.casefold())
    pos = sum(1 for t in tokens if t in POSITIVE)
    neg = sum(1 for t in tokens if t in NEGATIVE)
    if pos > neg:
        label, score = Sentiment.POSITIVE, pos
    elif neg > pos:
        label, score = Sentiment.NEGATIVE, neg
    else:
        label, score = Sentiment.NEUTRAL, 0
    confidence = min(0.99, 0.60 + 0.12 * score) if score else 0.50
    probs = {s.value: 0.1 for s in Sentiment}
    probs[label.value] = confidence
    remainder = 1 - confidence
    others = [s.value for s in Sentiment if s is not label]
    for other in others:
        probs[other] = remainder / 2
    return SentimentPrediction(label, round(confidence, 4), probs)
