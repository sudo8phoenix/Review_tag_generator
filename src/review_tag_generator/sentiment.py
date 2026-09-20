from __future__ import annotations

import re
from .schemas import Sentiment, SentimentPrediction

POSITIVE = {"amazing", "excellent", "great", "good", "love", "loved", "gorgeous", "sharp", "fast", "reliable", "wonderful"}
NEGATIVE = {"terrible", "bad", "poor", "hate", "hated", "awful", "slow", "weak", "worse", "broken", "barely", "disappointing"}
NEGATIONS = {"not", "never", "no", "isn't", "isnt", "wasn't", "wasnt", "hardly", "barely"}


def aspect_context_span(review: str, start_char: int, end_char: int, policy: str = "local_clause") -> tuple[str, int, int]:
    """Select context with offsets in the original review, even for repeated clauses."""
    if not 0 <= start_char < end_char <= len(review):
        raise ValueError("Aspect offsets must point inside the original review")
    if policy == "full_review":
        return review, 0, len(review)
    if policy != "local_clause":
        raise ValueError(f"Unknown sentiment context policy: {policy}")
    boundaries = [0]
    pattern = re.compile(r"\b(?:but|however|although|while)\b|[.!?]+(?=\s|$)", flags=re.I)
    for match in pattern.finditer(review):
        # Common abbreviations do not end a sentiment clause.
        if match.group().startswith(".") and re.search(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr)\.$", review[:match.end()], flags=re.I):
            continue
        boundaries.extend([match.start(), match.end()])
    boundaries.append(len(review))
    for raw_start, raw_end in zip(boundaries[::2], boundaries[1::2]):
        if raw_start <= start_char and end_char <= raw_end:
            fragment = review[raw_start:raw_end]
            stripped = fragment.strip()
            if not stripped:
                break
            start = raw_start + (len(fragment) - len(fragment.lstrip()))
            return stripped, start, start + len(stripped)
    return review, 0, len(review)


def aspect_context(review: str, start_char: int, end_char: int) -> str:
    return aspect_context_span(review, start_char, end_char)[0]


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
    pos = neg = 0
    for index, token in enumerate(tokens):
        if token not in POSITIVE and token not in NEGATIVE:
            continue
        negated = any(value in NEGATIONS - {"barely"} for value in tokens[max(0, index - 3):index])
        if (token in POSITIVE) != negated:
            pos += 1
        else:
            neg += 1
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
