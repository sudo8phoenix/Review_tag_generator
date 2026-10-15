# Review quality queue

Use the product insights queue to choose which saved predictions to inspect first.
It reads published model evidence; it does not change labels.

## Attention signals

`review_quality_queue(analyses, confidence_threshold=0.6)` derives the queue from
persisted analysis dictionaries. The threshold must be finite and within `[0, 1]`.

| Signal | Inclusion rule |
|---|---|
| Unknown aspect | At least one mention has no canonical aspect label and ID |
| Low confidence | A valid saved summary confidence is strictly below the threshold |
| No aspects | The review has no detected aspects |
| Contradictory sentiment | One canonical aspect has positive and negative predictions |

## Ordering and export

Queue order is deterministic: reviews with more distinct attention signals come first,
then review ID and original text provide stable tie-breaks. This ordering is for
workload triage only. A reason count or confidence value is not a measure of model
accuracy.

Each item includes the original review ID and text, backend, context policy, reason
codes and descriptions, minimum valid summary confidence, threshold, and the saved
aspect records with raw phrase, canonical fields, sentiment, probability values,
confidence fields, and source/context offsets. Offsets remain indices into the original
review text. The source review is included unchanged so an export remains interpretable.

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

The queue itself is review assistance only. Select a saved aspect prediction to
open the [review correction workflow](review-corrections.md), where reviewers can
record separate mapping/sentiment decisions. Use the
[full-review annotation workspace](review-annotations.md) for missing aspects,
boundary changes, false detections, and zero-aspect reviews. Queue rules do not claim measured
accuracy, create gold annotations, or feed reviewer decisions into training.

## Frontend endpoint contract

`GET /api/demo/products/{productId}/quality-queue` uses the currently published snapshot
and the default confidence threshold of 0.6. The client verifies the response snapshot
ID before showing or exporting the queue. Response shape:

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

Each item has `review_id`, `review_text`, `backend`, `context_policy`, `reasons`
(`{code,label}`), `minimum_confidence`, `confidence_threshold`, and `aspects` with raw
aspect, canonical aspect fields, sentiment, probabilities, confidence fields, and
source/context offsets. `snapshot_id` identifies the published product snapshot used by
the endpoint. The client compares it with the product page snapshot and hides mismatched
evidence. `stale` means processing or a version/revision difference makes the published
snapshot out of date; the returned queue still uses only published evidence.
