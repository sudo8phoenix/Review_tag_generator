"""Compare observed feedback in two persisted product detail snapshots.

The comparison describes model-labeled review feedback and its support. It is
not an estimate of objective product quality or a causal product difference.
"""

from __future__ import annotations

from typing import Any

MINIMUM_EVIDENCE_REVIEWS = 3


def _metadata(detail: dict[str, Any]) -> dict[str, Any]:
    product = detail.get("product") or {}
    insights = detail.get("insights") or {}
    return {
        "product": {"id": product.get("id"), "name": product.get("name")},
        "review_count": insights.get("review_count", 0),
        "snapshot_id": detail.get("snapshot_id"),
        "pipeline_version": detail.get("pipeline_version"),
        "aggregate_version": detail.get("aggregate_version"),
        "data_revision": detail.get("data_revision"),
        "stale": bool(detail.get("stale", False)),
    }


def _aspect_map(detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    aspects = (detail.get("insights") or {}).get("aspects") or []
    result: dict[str, dict[str, Any]] = {}
    for aspect in aspects:
        aspect_id = aspect.get("aspect_id")
        if not aspect_id:
            continue
        result[str(aspect_id)] = aspect
    return result


def _stats(aspect: dict[str, Any] | None) -> dict[str, Any] | None:
    if aspect is None:
        return None
    counts = aspect.get("counts") or {}
    review_count = int(aspect.get("review_count", 0) or 0)
    ratios = aspect.get("ratios") or {}
    return {
        "review_count": review_count,
        "positive": int(counts.get("positive", 0) or 0),
        "neutral": int(counts.get("neutral", 0) or 0),
        "negative": int(counts.get("negative", 0) or 0),
        "positive_share": float(ratios.get("positive", 0) or 0),
        "neutral_share": float(ratios.get("neutral", 0) or 0),
        "negative_share": float(ratios.get("negative", 0) or 0),
        "classification": aspect.get("classification"),
    }


def compare_products(left_detail: dict[str, Any], right_detail: dict[str, Any]) -> dict[str, Any]:
    """Compare canonical aspects present in two ``Repository.detail`` snapshots.

    Aspect rows remain visible at any support level. A favorable-share
    difference and directional signal are emitted only when both aspects have
    at least three supporting reviews. The difference is the left positive
    share minus negative share, less the corresponding right value.
    """
    left_aspects, right_aspects = _aspect_map(left_detail), _aspect_map(right_detail)
    pipeline_mismatch = (
        left_detail.get("pipeline_version") != right_detail.get("pipeline_version")
    )
    rows = []
    for aspect_id in sorted(left_aspects.keys() | right_aspects.keys()):
        left_aspect = left_aspects.get(aspect_id)
        right_aspect = right_aspects.get(aspect_id)
        source = left_aspect or right_aspect or {}
        left, right = _stats(left_aspect), _stats(right_aspect)
        left_supported = left is not None and left["review_count"] >= MINIMUM_EVIDENCE_REVIEWS
        right_supported = right is not None and right["review_count"] >= MINIMUM_EVIDENCE_REVIEWS
        difference = None
        signal = "insufficient_evidence"
        if left_supported and right_supported and not pipeline_mismatch:
            difference = (left["positive_share"] - left["negative_share"]) - (
                right["positive_share"] - right["negative_share"]
            )
            signal = "left" if difference > 0 else "right" if difference < 0 else "tie"
        rows.append({
            "aspect_id": aspect_id,
            "aspect": source.get("aspect", aspect_id),
            "left": left,
            "right": right,
            "evidence_gap": {
                "left": not left_supported,
                "right": not right_supported,
                "pipeline_version_mismatch": pipeline_mismatch,
            },
            "favorable_share_difference": difference,
            "signal": signal,
        })
    return {
        "left": _metadata(left_detail),
        "right": _metadata(right_detail),
        "minimum_evidence_reviews": MINIMUM_EVIDENCE_REVIEWS,
        "pipeline_version_mismatch": pipeline_mismatch,
        "interpretation": "Observed predicted feedback in saved reviews; not objective product quality. Results depend on review sampling and model labeling.",
        "rows": rows,
    }
