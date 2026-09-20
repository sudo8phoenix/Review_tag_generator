"""Deterministic aggregation of already-saved review analyses.

The M07 API below performs no extraction, normalization model work, or sentiment
inference.  ``aggregate`` remains as a compatibility adapter for the original
prototype; new product snapshots should use ``aggregate_saved_analyses``.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from .normalization import get_ontology, normalize_aspect
from .schemas import ProductAggregate, Review, Sentiment, TagResult
from .tags import generate_tag


def aggregate(product_id: str, rows: list[tuple[Review, list[TagResult]]]) -> ProductAggregate:
    aspect_counts, sentiments = Counter(), Counter()
    grouped = defaultdict(list)
    for review, tags in rows:
        for tag in tags:
            if tag.normalized_aspect is None:
                continue
            aspect_counts[tag.normalized_aspect] += 1
            sentiments[tag.sentiment.value] += 1
            grouped[(tag.normalized_aspect, tag.sentiment)].append((review, tag))

    def ranked(sentiment):
        out = []
        for (aspect, label), values in grouped.items():
            if label is sentiment:
                out.append({"aspect": aspect, "tag": values[0][1].tag, "mentions": len(values), "ratio": round(len(values) / max(aspect_counts[aspect], 1), 4)})
        return sorted(out, key=lambda x: (-x["mentions"], x["aspect"]))

    representatives = []
    for (aspect, label), values in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0])):
        review, tag = values[0]
        representatives.append({"aspect": aspect, "sentiment": label.value, "review_id": review.review_id, "review_text": review.review_text, "tag": tag.tag})
    return ProductAggregate(product_id, ranked(Sentiment.POSITIVE), ranked(Sentiment.NEGATIVE), dict(sentiments), dict(aspect_counts), representatives)


@dataclass(frozen=True)
class SavedReviewAnalysis:
    """One persisted analysis, paired with its original saved review."""

    review: Review
    mentions: Sequence[TagResult]


@dataclass(frozen=True)
class ProductAggregateSnapshot:
    """Reproducible M07 snapshot DTO; nested objects are JSON-ready mappings."""

    product_id: str
    review_count: int
    sentiment_distribution: dict[str, int]
    aspects: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    mixed: list[str]
    neutral: list[str]
    insufficient_evidence: list[str]
    top_tags: list[dict]
    representative_reviews: list[dict]


_ASPECT_LABELS = {item.id: item.display_label for item in get_ontology().aspects}
_ASPECT_IDS = set(_ASPECT_LABELS)
def _canonical_id(value: str | None) -> str | None:
    """Resolve a saved canonical ID or display/alias to the v1 stable ID.

    This is a static alias lookup only.  Unknown mentions remain in per-review
    analyses and are deliberately excluded from product-level canonical totals.
    """
    if not value:
        return None
    candidate = value.strip()
    if candidate in _ASPECT_IDS:
        return candidate
    result = normalize_aspect(candidate)
    if result.normalized_aspect is None:
        return None
    # The normalizer is alias-only by default. Resolve its display label back
    # to the stable ID rather than leaking presentation labels into aggregates.
    for aspect_id, label in _ASPECT_LABELS.items():
        if label == result.normalized_aspect:
            return aspect_id
    return None


def _validate_analysis(product_id: str, row: SavedReviewAnalysis) -> None:
    if row.review.product_id != product_id:
        raise ValueError(f"review {row.review.review_id!r} belongs to a different product")
    for mention in row.mentions:
        if not isinstance(mention.sentiment, Sentiment):
            raise ValueError("saved mention sentiment must be a Sentiment value")
        if not math.isfinite(mention.confidence) or not 0.0 <= mention.confidence <= 1.0:
            raise ValueError("saved mention confidence must be finite and between 0 and 1")


def aggregate_saved_analyses(
    product_id: str,
    analyses: Iterable[SavedReviewAnalysis],
    *,
    top_k: int = 10,
    representative_limit: int = 3,
) -> ProductAggregateSnapshot:
    """Aggregate validated saved analyses into a deterministic product snapshot.

    A repeated review ID is deduplicated when its saved review and mentions are
    identical; conflicting rows for one ID are rejected. Each review contributes
    exactly one vote per canonical aspect. All evidence mentioned for that vote
    participates in its confidence minimum.
    """
    if not product_id:
        raise ValueError("product_id must be non-empty")
    if top_k < 0:
        raise ValueError("top_k must be non-negative")
    if representative_limit < 0:
        raise ValueError("representative_limit must be non-negative")

    # Key rows by review ID so duplicate inputs cannot multiply votes. Compare
    # normalized immutable representations to make conflict detection explicit.
    unique: dict[str, SavedReviewAnalysis] = {}
    for row in analyses:
        _validate_analysis(product_id, row)
        review_id = row.review.review_id
        existing = unique.get(review_id)
        if existing is None:
            unique[review_id] = row
        elif existing != row:
            raise ValueError(f"conflicting saved analyses for review {review_id!r}")

    # A vote record stores exactly the mentions supporting its displayed vote.
    grouped: dict[str, list[dict]] = defaultdict(list)
    mention_counts: Counter[str] = Counter()
    contradictions: Counter[str] = Counter()
    vote_distribution: Counter[str] = Counter()

    for review_id in sorted(unique):
        row = unique[review_id]
        by_aspect: dict[str, list[tuple[int, TagResult]]] = defaultdict(list)
        for ordinal, mention in enumerate(row.mentions):
            aspect_id = _canonical_id(
                getattr(mention, "normalized_aspect_id", None)
                or mention.normalized_aspect
            )
            if aspect_id is None:
                continue
            by_aspect[aspect_id].append((ordinal, mention))

        for aspect_id, indexed_mentions in by_aspect.items():
            mention_counts[aspect_id] += len(indexed_mentions)
            labels = {mention.sentiment for _, mention in indexed_mentions}
            contradictory = Sentiment.POSITIVE in labels and Sentiment.NEGATIVE in labels
            if contradictory:
                vote = Sentiment.NEUTRAL
                contradictions[aspect_id] += 1
                supporting = [
                    (ordinal, mention)
                    for ordinal, mention in indexed_mentions
                    if mention.sentiment in (Sentiment.POSITIVE, Sentiment.NEGATIVE)
                ]
                evidence_type = "mixed_within_review"
            elif Sentiment.POSITIVE in labels:
                vote = Sentiment.POSITIVE
                supporting = [(i, m) for i, m in indexed_mentions if m.sentiment is vote]
                evidence_type = "mention"
            elif Sentiment.NEGATIVE in labels:
                vote = Sentiment.NEGATIVE
                supporting = [(i, m) for i, m in indexed_mentions if m.sentiment is vote]
                evidence_type = "mention"
            else:
                vote = Sentiment.NEUTRAL
                supporting = [(i, m) for i, m in indexed_mentions if m.sentiment is vote]
                evidence_type = "mention"

            confidence = min(mention.confidence for _, mention in indexed_mentions)
            mention_evidence = [
                {
                    "start_char": mention.start_char,
                    "end_char": mention.end_char,
                    "raw_aspect": mention.raw_aspect,
                    "sentiment": mention.sentiment.value,
                    "tag": mention.tag,
                    "confidence": mention.confidence,
                }
                for ordinal, mention in sorted(
                    supporting,
                    key=lambda pair: (
                        pair[1].start_char,
                        pair[1].end_char,
                        pair[1].raw_aspect,
                        pair[1].sentiment.value,
                        pair[1].tag,
                        pair[1].confidence,
                        pair[0],
                    ),
                )
            ]
            grouped[aspect_id].append({
                "review_id": review_id,
                "review_text": row.review.review_text,
                "helpful_votes": row.review.helpful_votes,
                "vote": vote,
                "confidence": confidence,
                "evidence_type": evidence_type,
                "mentions": mention_evidence,
            })
            vote_distribution[vote.value] += 1

    aspects: list[dict] = []
    class_ids: dict[str, list[str]] = {
        key: [] for key in ("strengths", "weaknesses", "mixed", "neutral", "insufficient_evidence")
    }
    for aspect_id, votes in grouped.items():
        votes.sort(key=lambda v: v["review_id"])
        review_count = len(votes)
        counts = {sentiment.value: 0 for sentiment in Sentiment}
        for item in votes:
            counts[item["vote"].value] += 1
        ratios = {label: counts[label] / review_count for label in counts}
        positive_ratio = ratios[Sentiment.POSITIVE.value]
        negative_ratio = ratios[Sentiment.NEGATIVE.value]
        average_confidence = math.fsum(v["confidence"] for v in votes) / review_count
        score = math.log1p(review_count) * average_confidence * abs(positive_ratio - negative_ratio)

        if review_count < 3:
            classification = "insufficient_evidence"
            bucket = "insufficient_evidence"
        elif counts[Sentiment.POSITIVE.value] == 0 and counts[Sentiment.NEGATIVE.value] == 0:
            classification = "neutral"
            bucket = "neutral"
        elif positive_ratio >= 0.80:
            classification = "excellent"
            bucket = "strengths"
        elif positive_ratio >= 0.60:
            classification = "good"
            bucket = "strengths"
        elif negative_ratio >= 0.70:
            classification = "poor"
            bucket = "weaknesses"
        elif negative_ratio >= 0.50:
            classification = "weak"
            bucket = "weaknesses"
        else:
            classification = "mixed"
            bucket = "mixed"
        if classification in ("excellent", "good"):
            aggregate_tag = generate_tag(aspect_id, Sentiment.POSITIVE)
        elif classification in ("poor", "weak"):
            aggregate_tag = generate_tag(aspect_id, Sentiment.NEGATIVE)
        elif classification == "neutral":
            aggregate_tag = generate_tag(aspect_id, Sentiment.NEUTRAL)
        elif classification == "mixed":
            aggregate_tag = f"Mixed {_ASPECT_LABELS[aspect_id]} Feedback"
        else:
            aggregate_tag = None
        class_ids[bucket].append(aspect_id)
        aspects.append({
            "aspect_id": aspect_id,
            "aspect": _ASPECT_LABELS[aspect_id],
            "mention_count": mention_counts[aspect_id],
            "review_count": review_count,
            "contradictory_review_count": contradictions[aspect_id],
            "counts": counts,
            "ratios": ratios,
            "average_confidence": average_confidence,
            "score": score,
            "classification": classification,
            "rank": None,
            "aggregate_tag": aggregate_tag,
        })

    supported = [aspect for aspect in aspects if aspect["classification"] != "insufficient_evidence"]
    supported.sort(key=lambda a: (-a["score"], -a["review_count"], a["aspect_id"]))
    for rank, aspect in enumerate(supported, start=1):
        aspect["rank"] = rank
    aspects.sort(key=lambda a: (a["rank"] is None, a["rank"] or 0, a["aspect_id"]))
    for bucket in class_ids:
        class_ids[bucket].sort(key=lambda aspect_id: next(
            a["rank"] for a in aspects if a["aspect_id"] == aspect_id
        ) if bucket != "insufficient_evidence" else aspect_id)

    ranked_tags = [
        {
            "aspect_id": aspect["aspect_id"],
            "aspect": aspect["aspect"],
            "classification": aspect["classification"],
            "aggregate_tag": aspect["aggregate_tag"],
            "score": aspect["score"],
            "rank": aspect["rank"],
        }
        for aspect in supported
        if aspect["classification"] in ("excellent", "good", "poor", "weak", "mixed", "neutral")
    ][:top_k]

    representatives: list[dict] = []
    for aspect_id in sorted(grouped):
        votes = grouped[aspect_id]
        for sentiment in Sentiment:
            matching = [vote for vote in votes if vote["vote"] is sentiment]
            matching.sort(key=lambda v: (-v["confidence"], -v["helpful_votes"], v["review_id"]))
            for vote in matching[:representative_limit]:
                representatives.append({
                    "aspect_id": aspect_id,
                    "sentiment": sentiment.value,
                    "review_id": vote["review_id"],
                    "review_text": vote["review_text"],
                    "confidence": vote["confidence"],
                    "helpful_votes": vote["helpful_votes"],
                    "evidence_type": vote["evidence_type"],
                    "mentions": vote["mentions"],
                })

    distribution = {sentiment.value: vote_distribution[sentiment.value] for sentiment in Sentiment}
    return ProductAggregateSnapshot(
        product_id=product_id,
        review_count=len(unique),
        sentiment_distribution=distribution,
        aspects=aspects,
        strengths=class_ids["strengths"],
        weaknesses=class_ids["weaknesses"],
        mixed=class_ids["mixed"],
        neutral=class_ids["neutral"],
        insufficient_evidence=class_ids["insufficient_evidence"],
        top_tags=ranked_tags,
        representative_reviews=representatives,
    )
