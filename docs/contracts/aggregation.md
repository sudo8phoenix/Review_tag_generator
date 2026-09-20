# Product aggregation contract (M07)

`review_tag_generator.aggregation.aggregate_saved_analyses` turns saved review
analyses into a deterministic product snapshot. It is a pure in-memory function:
it does not load models, make network calls, inspect ratings, or rerun analysis.
The caller supplies `product_id` and an iterable of
`SavedReviewAnalysis(review: Review, mentions: Sequence[TagResult])`. The review
and mention values must already have passed persistence/API validation. A
mention's `normalized_aspect` may contain a stable ontology ID, canonical label,
or known alias. IDs are used in the output; unknown aspects are omitted from
product aggregates while remaining available on the saved review analysis.

## Counting and voting

`mention_count` is the number of known canonical mentions, including repeated
mentions and aliases in the same review. `review_count` is the number of
distinct saved review IDs mentioning that aspect. An exact duplicate row for a
review ID is ignored; conflicting saved rows with the same ID are rejected.
Rows belonging to another product and non-finite or out-of-range mention
confidence are rejected.

Each distinct review contributes one vote per aspect. Positive and negative
mentions together produce one neutral vote and increment
`contradictory_review_count`; the representative is marked
`evidence_type="mixed_within_review"` and includes both opposing mentions. In
all other cases, any positive mention wins over neutral mentions, any negative
mention wins over neutral mentions, and an all-neutral group votes neutral.
Vote confidence is the minimum confidence across all mentions for that review
and aspect. Sentiment counts and product sentiment distribution count these
votes, never raw mentions, star ratings, or model predictions. Ratios explicitly
include all three labels and divide by that aspect's distinct review count.

## Classification and ranking

Aspects with fewer than three distinct reviews are `insufficient_evidence` and
have no rank; they do not appear in top tags, strengths, weaknesses, mixed, or
neutral groups. With sufficient support, all-neutral votes classify as
`neutral`. Otherwise positive ratio `>= .80` is `excellent`, `>= .60` is
`good`; negative ratio `>= .70` is `poor`, `>= .50` is `weak`; remaining
aspects are `mixed`. The groups partition IDs: `strengths` includes excellent
and good, `weaknesses` includes poor and weak, and `mixed` and `neutral` remain
separate.

`aggregate_tag` uses the M06 aspect-specific template for positive strength,
negative weakness, or all-neutral classification. Mixed aspects use the
deterministic wording `Mixed <Display Label> Feedback`. Insufficient-evidence
aspects have a null aggregate tag.

Score is the unrounded value
`log1p(review_count) * average_vote_confidence * abs(positive_ratio - negative_ratio)`.
There is no helpful-vote multiplier. Supported aspects sort by score descending,
review count descending, then canonical ID ascending; ranks start at one. The
`top_k` list contains the first supported aspects, including neutral and mixed
classifications. Zero-count sentiment labels are always present. Empty products
return zero sentiment counters and empty collections. No rounded intermediate
values or NaN values are emitted.

For each aspect and aggregate sentiment, up to three representative reviews
are selected by vote confidence descending, `helpful_votes` descending, then
review ID ascending. A review can appear only once in a given aspect/sentiment
group. Positive and negative representatives include only mentions supporting
that label. Ordinary neutral representatives include neutral mentions;
contradictory votes are explicitly marked as mixed within the review and show
the opposing source mentions rather than presenting them as purely neutral.

The legacy `aggregate()` function remains available for the original prototype
pipeline. New persistence and API integration should use the typed saved-analysis
API above and serialize its snapshot with `dataclasses.asdict`.
