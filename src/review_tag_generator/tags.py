"""Customer-facing tag wording for the versioned electronics ontology."""

from __future__ import annotations

import re

from .normalization import get_ontology
from .schemas import Sentiment


# Tuples are ordered positive, negative, neutral. The wording is deliberately
# explicit per canonical ID so changing labels never silently changes a tag.
_TEMPLATES: dict[str, dict[Sentiment, str]] = {
    "battery": {Sentiment.POSITIVE: "Great Battery", Sentiment.NEGATIVE: "Poor Battery", Sentiment.NEUTRAL: "Neutral Battery Feedback"},
    "display": {Sentiment.POSITIVE: "Great Display", Sentiment.NEGATIVE: "Poor Display", Sentiment.NEUTRAL: "Neutral Display Feedback"},
    "performance": {Sentiment.POSITIVE: "Great Performance", Sentiment.NEGATIVE: "Poor Performance", Sentiment.NEUTRAL: "Neutral Performance Feedback"},
    "processor": {Sentiment.POSITIVE: "Great Processor", Sentiment.NEGATIVE: "Poor Processor", Sentiment.NEUTRAL: "Neutral Processor Feedback"},
    "keyboard": {Sentiment.POSITIVE: "Great Keyboard", Sentiment.NEGATIVE: "Poor Keyboard", Sentiment.NEUTRAL: "Neutral Keyboard Feedback"},
    "trackpad": {Sentiment.POSITIVE: "Great Trackpad", Sentiment.NEGATIVE: "Poor Trackpad", Sentiment.NEUTRAL: "Neutral Trackpad Feedback"},
    "camera": {Sentiment.POSITIVE: "Great Camera", Sentiment.NEGATIVE: "Poor Camera", Sentiment.NEUTRAL: "Neutral Camera Feedback"},
    "speakers": {Sentiment.POSITIVE: "Great Speakers", Sentiment.NEGATIVE: "Poor Speakers", Sentiment.NEUTRAL: "Neutral Speakers Feedback"},
    "storage": {Sentiment.POSITIVE: "Great Storage", Sentiment.NEGATIVE: "Poor Storage", Sentiment.NEUTRAL: "Neutral Storage Feedback"},
    "ram": {Sentiment.POSITIVE: "Great RAM", Sentiment.NEGATIVE: "Poor RAM", Sentiment.NEUTRAL: "Neutral RAM Feedback"},
    "build_quality": {Sentiment.POSITIVE: "Solid Build", Sentiment.NEGATIVE: "Poor Build Quality", Sentiment.NEUTRAL: "Neutral Build Quality Feedback"},
    "weight": {Sentiment.POSITIVE: "Low Weight", Sentiment.NEGATIVE: "Heavy Build", Sentiment.NEUTRAL: "Neutral Weight Feedback"},
    "design": {Sentiment.POSITIVE: "Great Design", Sentiment.NEGATIVE: "Poor Design", Sentiment.NEUTRAL: "Neutral Design Feedback"},
    "price": {Sentiment.POSITIVE: "Affordable Price", Sentiment.NEGATIVE: "High Price", Sentiment.NEUTRAL: "Neutral Price Feedback"},
    "value": {Sentiment.POSITIVE: "Good Value", Sentiment.NEGATIVE: "Poor Value", Sentiment.NEUTRAL: "Neutral Value Feedback"},
    "heating": {Sentiment.POSITIVE: "Runs Cool", Sentiment.NEGATIVE: "Overheats", Sentiment.NEUTRAL: "Neutral Heating Feedback"},
    "charging": {Sentiment.POSITIVE: "Great Charging", Sentiment.NEGATIVE: "Poor Charging", Sentiment.NEUTRAL: "Neutral Charging Feedback"},
    "ports": {Sentiment.POSITIVE: "Great Ports", Sentiment.NEGATIVE: "Poor Ports", Sentiment.NEUTRAL: "Neutral Ports Feedback"},
    "delivery": {Sentiment.POSITIVE: "Fast Delivery", Sentiment.NEGATIVE: "Late Delivery", Sentiment.NEUTRAL: "Neutral Delivery Feedback"},
    "packaging": {Sentiment.POSITIVE: "Great Packaging", Sentiment.NEGATIVE: "Poor Packaging", Sentiment.NEUTRAL: "Neutral Packaging Feedback"},
    "customer_service": {Sentiment.POSITIVE: "Helpful Customer Service", Sentiment.NEGATIVE: "Poor Customer Service", Sentiment.NEUTRAL: "Neutral Customer Service Feedback"},
}

_ONTOLOGY = get_ontology()
if set(_TEMPLATES) != set(_ONTOLOGY.by_id):  # fail fast if ontology coverage drifts
    raise RuntimeError("tag templates must cover every canonical ontology ID exactly once")
_LABEL_TO_ID = {aspect.display_label.casefold(): aspect.id for aspect in _ONTOLOGY.aspects}
# Underscores distinguish ID-shaped input from ordinary unknown aspect words
# such as "hinge", which should stay visible upstream and produce no tag.
_CANONICAL_ID = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]*\Z")


def generate_tag(normalized_aspect: str | None, sentiment: Sentiment | str) -> str | None:
    """Generate a stable, deterministic tag; unknown aspects have no tag.

    Stable canonical IDs are preferred. Display labels remain accepted for the
    original pipeline and other callers. Unrecognized raw aspect text yields
    ``None``; a syntactically valid but unknown canonical ID is a validation
    error so ontology/version mismatches are visible.
    """
    try:
        label = sentiment if isinstance(sentiment, Sentiment) else Sentiment(sentiment)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid sentiment: {sentiment!r}") from exc

    if normalized_aspect is None:
        return None
    if not isinstance(normalized_aspect, str) or not normalized_aspect.strip():
        return None

    value = normalized_aspect.strip()
    canonical_id = value if value in _TEMPLATES else _LABEL_TO_ID.get(value.casefold())
    if canonical_id is None:
        if _CANONICAL_ID.fullmatch(value):
            raise ValueError(f"unknown canonical aspect ID: {value!r}")
        return None
    return _TEMPLATES[canonical_id][label]
