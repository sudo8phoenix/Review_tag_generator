# Product feedback comparison

`review_tag_generator.comparison.compare_products(left_detail, right_detail)` compares
two mappings returned by `Repository.detail`. It reads only their published insight
snapshots and does not run inference.

## Response and provenance

The response includes metadata for each product: ID and name, saved-review count,
snapshot ID, pipeline and aggregate versions, data revision, and whether the snapshot is
stale. `rows` contains the sorted union of canonical `aspect_id` values. Each row has
the display aspect, per-side review support and positive/neutral/negative counts and
shares (or `null` when the aspect is absent), an `evidence_gap`, a
`favorable_share_difference`, and a `signal`.

## Support and directional signal

An aspect is supported with at least three review votes on each side. A directional
difference is available only when both sides meet that threshold and the pipeline
versions match. It is computed as `(left positive share - left negative share) - (right
positive share - right negative share)`. The signal is `left`, `right`, or `tie`;
otherwise it is `insufficient_evidence` and the difference is `null`. The gap object
names sides below the support threshold and whether pipeline versions differ. Three
votes are a minimum evidence gate, not a guarantee of precision.

## Interpretation limits

These results describe **observed predicted feedback** in saved reviews. They do not
establish objective product quality, buyer preference, or causal effects. Review
sampling, selection, wording, time period, and model labeling can all affect the
apparent distribution. Stale snapshots may omit newly saved reviews or reflect an older
pipeline. Product and snapshot provenance should therefore accompany any interpretation.

## API and interface

The frontend panel in `frontend/src/components/ProductComparisonPanel.tsx` expects a GET
response with this contract from
`/api/demo/products/{productId}/compare/{otherProductId}`. The route is intentionally
owned by the application integration layer.
