"""Deterministic suggestions for which saved reviews may merit human attention.

This module reports review signals only. It does not assign corrected labels,
estimate accuracy, or use human feedback to retrain a model.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any


_REASON_TEXT = {
    "unknown_aspect": "At least one aspect could not be mapped to a canonical aspect.",
    "low_confidence": "At least one aspect has a confidence score below the review threshold.",
    "no_aspects": "No aspects were returned for this review.",
    "contradictory_sentiment": "The same canonical aspect has both positive and negative predictions.",
}


def _confidence_values(tags: list[Mapping[str, Any]]) -> list[float]:
    values: list[float] = []
    for tag in tags:
        value = tag.get("confidence")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number) and 0 <= number <= 1:
                values.append(number)
    return values


def _canonical_key(tag: Mapping[str, Any]) -> str | None:
    aspect_id = tag.get("normalized_aspect_id")
    if isinstance(aspect_id, str) and aspect_id.strip():
        return aspect_id.strip().casefold()
    aspect = tag.get("normalized_aspect")
    if isinstance(aspect, str) and aspect.strip():
        return " ".join(aspect.split()).casefold()
    return None


def _has_contradiction(tags: list[Mapping[str, Any]]) -> bool:
    sentiments: dict[str, set[str]] = {}
    for tag in tags:
        key = _canonical_key(tag)
        sentiment = tag.get("sentiment")
        if key and sentiment in {"positive", "negative"}:
            sentiments.setdefault(key, set()).add(sentiment)
    return any(labels == {"positive", "negative"} for labels in sentiments.values())


def _export_tag(tag: Mapping[str, Any]) -> dict[str, Any]:
    """Keep prediction provenance and source spans intact for review/export."""
    fields = (
        "raw_aspect",
        "normalized_aspect",
        "normalized_aspect_id",
        "normalization_method",
        "normalization_similarity",
        "sentiment",
        "confidence",
        "aspect_confidence",
        "sentiment_confidence",
        "probabilities",
        "tag",
        "start_char",
        "end_char",
        "context_start_char",
        "context_end_char",
    )
    return {key: tag[key] for key in fields if key in tag}


def review_quality_queue(
    analyses: Iterable[Mapping[str, Any]], confidence_threshold: float = 0.6
) -> dict[str, Any]:
    """Return deterministic, export-friendly suggestions for human review.

    ``confidence_threshold`` applies to the saved per-aspect summary
    ``confidence``. Missing or invalid confidence values do not themselves
    create a low-confidence reason.
    """
    if (
        isinstance(confidence_threshold, bool)
        or not isinstance(confidence_threshold, (int, float))
        or not math.isfinite(float(confidence_threshold))
        or not 0 <= float(confidence_threshold) <= 1
    ):
        raise ValueError("confidence_threshold must be finite and between 0 and 1")
    threshold = float(confidence_threshold)

    items: list[dict[str, Any]] = []
    for analysis in analyses:
        review = analysis.get("review")
        if not isinstance(review, Mapping):
            continue
        raw_tags = analysis.get("tags")
        tags = [tag for tag in raw_tags if isinstance(tag, Mapping)] if isinstance(raw_tags, list) else []

        reasons: list[str] = []
        if any(tag.get("normalized_aspect") is None and tag.get("normalized_aspect_id") is None for tag in tags):
            reasons.append("unknown_aspect")
        confidences = _confidence_values(tags)
        minimum = min(confidences) if confidences else None
        if minimum is not None and minimum < threshold:
            reasons.append("low_confidence")
        if not tags:
            reasons.append("no_aspects")
        if _has_contradiction(tags):
            reasons.append("contradictory_sentiment")
        if not reasons:
            continue

        reason_records = [{"code": code, "label": _REASON_TEXT[code]} for code in reasons]
        items.append(
            {
                "review_id": review.get("review_id"),
                "review_text": review.get("review_text", ""),
                "backend": analysis.get("backend"),
                "context_policy": analysis.get("context_policy"),
                "reasons": reason_records,
                "minimum_confidence": minimum,
                "confidence_threshold": threshold,
                "aspects": [_export_tag(tag) for tag in tags],
            }
        )

    # Rank by number of independent attention signals, then stable review ID.
    # The count is only a queue ordering aid, not a quality or accuracy score.
    items.sort(key=lambda item: (-len(item["reasons"]), str(item["review_id"] or ""), str(item["review_text"])))
    counts = Counter(reason["code"] for item in items for reason in item["reasons"])
    return {
        "items": items,
        "summary": {
            "queued_reviews": len(items),
            "reason_counts": {code: counts.get(code, 0) for code in _REASON_TEXT},
            "confidence_threshold": threshold,
        },
        "disclaimer": "Suggested review priorities only; not gold labels, accuracy estimates, or retraining data.",
    }
