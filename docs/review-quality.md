# Review quality queue

`review_quality_queue(analyses, confidence_threshold=0.6)` derives an advisory queue from persisted analysis dictionaries. It includes reviews when at least one aspect has no canonical aspect label and ID, a valid saved summary confidence strictly below the threshold, the review has no aspects, or one canonical aspect has both positive and negative predicted sentiment. The threshold must be finite and within `[0, 1]`.

Queue order is deterministic: reviews with more distinct attention signals come first, then review ID and original text provide stable tie-breaks. This ordering is for workload triage only. A reason count or confidence value is not a measure of model accuracy.

Each item includes the original review ID and text, backend, context policy, reason codes and descriptions, minimum valid summary confidence, threshold, and the saved aspect records with raw phrase, canonical fields, sentiment, probability values, confidence fields, and source/context offsets. Offsets remain indices into the original review text. The source review is included unchanged so an export remains interpretable.

The function returns:

```json
{
  "items": [],
  "summary": {
    "queued_reviews": 0,
    "reason_counts": {
      "unknown_aspect": 0,
      "low_confidence": 0,
      "no_aspects": 0,
      "contradictory_sentiment": 0
    },
    "confidence_threshold": 0.6
  },
  "disclaimer": "Suggested review priorities only; not gold labels, accuracy estimates, or retraining data."
}
```

This is review assistance only. It does not propose corrected labels, claim measured accuracy, create gold annotations, or feed reviewer decisions into training.

## Frontend endpoint contract

`GET /api/demo/products/{productId}/quality-queue` uses the currently published snapshot and the default confidence threshold of 0.6. The client verifies the response snapshot ID before showing or exporting the queue. Response shape:

```json
{
  "items": [],
  "summary": {
    "queued_reviews": 0,
    "reason_counts": {},
    "confidence_threshold": 0.6
  },
  "snapshot_id": "snapshot identifier or null",
  "stale": false,
  "disclaimer": "Suggested review priorities only; not gold labels, accuracy estimates, or retraining data."
}
```

Each item has `review_id`, `review_text`, `backend`, `context_policy`, `reasons` (`{code,label}`), `minimum_confidence`, `confidence_threshold`, and `aspects` with raw aspect, canonical aspect fields, sentiment, probabilities, confidence fields, and source/context offsets. `snapshot_id` identifies the published product snapshot used by the endpoint. The client compares it with the product page snapshot and hides mismatched evidence. `stale` means processing or a version/revision difference makes the published snapshot out of date; the returned queue still uses only published evidence.
