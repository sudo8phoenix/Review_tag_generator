# Review annotation workspace

Product insights now include an **Annotation workspace** for all successfully
analyzed reviews in the published snapshot, including reviews where the model
detected no aspects. This extends the existing per-aspect correction workflow
into full-review annotation with progress tracking.

## Annotate a review

1. Select a status filter: **Needs review**, **Reviewed**, **Needs adjudication**,
   or **All reviews**. Progress counts always cover the entire published workset.
2. Choose **Annotate review**. The editor starts from the latest saved annotation.
   If there is no annotation, it starts from model mentions with existing explicit
   aspect corrections applied to the draft. Neither starting point is marked
   complete automatically.
3. Select a missing phrase in the read-only source text and choose **Add selected
   phrase**. Choose its category and sentiment. Unknown is an explicit category
   decision; new mentions initially have neutral sentiment for the reviewer to check.
4. Correct boundaries with the start/end fields or select the intended source
   text and choose **Use selection for aspect …**. Remove false detections with
   **Remove aspect …**. All saved spans must be exact, nonempty and nonoverlapping.
5. Enter a reviewer name and review notes. **Save draft** keeps progress at
   Needs review. **Needs adjudication** records an unresolved review. **Mark
   reviewed** records full-review completion; **Mark reviewed & next** also opens
   the next item needing review in the active filter.

If no explicit aspects remain, check **I checked the full review and found no
explicit aspects** before marking it reviewed. A zero-detection model result
alone never completes a review. Save a draft before closing to retain edits;
unsaved changes are kept during request failures but not after closing/reloading.
Collapsed sections preserve original predictions, aspect-decision history and
full annotation revision history for inspection.

Positions use zero-based Unicode code points, with an exclusive end. Textarea
selections are converted from browser UTF-16 positions and normalized line breaks
back to the original source text, including emoji and CRLF/CR input. Source text
itself is never rewritten to match an annotation.

## Status and provenance

Annotations are append-only revisions associated with an exact saved analysis
run. Each revision stores the reviewer, notes, status, source-text hash, pipeline
and ontology versions, previous annotation ID, current aspect-correction revision,
explicit mentions and original model predictions. Reviewer names and completion
are self-reported in the local app; **Reviewed** is not independent adjudication
or certification of gold labels.

The same analysis run retains its progress when included in a newer product
snapshot. A different pipeline's analysis run starts a separate annotation history.
If any new per-aspect correction is recorded after annotation, effective progress
returns to Needs review. The editor shows the change and its decision history;
the reviewer must reconcile it explicitly. Annotations do not silently overwrite
one another or acknowledge a concurrently changed aspect decision.

Writes check the currently published snapshot, annotation revision and latest
aspect-decision revision under the owning product lock. Stale writes return 409.
The editor keeps the conflicting draft until the reviewer explicitly chooses
**Reload saved annotation**. Unchanged retries reuse their request UUID; identical
requests return the saved revision, while changed requests with that ID conflict.

Saved annotations are separate from model predictions, aggregate votes, product
totals, alias definitions and training. No automatic retraining or evaluation
claims follow from marking a review complete.

## Export and deletion

**Export annotations** downloads the latest saved revision for each annotated
analysis in the currently published snapshot. Each entry contains the original
review text, mentions, provenance, saved status and effective status. Reviews
without any saved annotation are absent; use worklist counts to identify remaining
work. A saved Reviewed status with later aspect changes exports as effective
Needs review. Drafts and adjudication items remain explicitly labeled.

This JSON is separate from the existing per-aspect decision export and from the
offline dataset's automated proposals. Do not treat it as an independently
reviewed held-out score. Raw exported text is local data and should remain outside
Git as with other review datasets.

Deleting a review or its analysis cascades annotation removal. Removing one
import preserves annotations on other surviving reviews even when old product
snapshots are removed. Clearing a product's reviews or deleting the product removes
its annotations.

## API and deployment

| Endpoint | Purpose |
|---|---|
| `GET /api/demo/products/{id}/annotations` | Worklist, status filter and complete progress counts |
| `GET /api/demo/products/{id}/annotations/{review_id}` | Full-review draft, source predictions and history |
| `POST /api/demo/products/{id}/annotations` | Append an annotation/status revision |
| `GET /api/demo/products/{id}/annotations/export` | Latest saved annotations for a published snapshot |

Detail and export requests require the snapshot UUID. Worklist accepts
`snapshot_id` and `status` (`all`, `needs_review`, `reviewed`, `needs_adjudication`).
POSTs require `snapshot_id`, `review_id`, `request_id`, reviewer, reason, status,
mentions and the expected previous annotation/correction IDs. Each mention requires
`raw_aspect`, `start_char`, `end_char`, `canonical_id` (explicit null for unknown),
and positive/neutral/negative sentiment. Empty completed reviews also require
`confirmed_no_aspects: true`.

PostgreSQL deployments require `alembic upgrade head` through migration
`0005_review_annotations`. Local SQLite startup creates the added table without
replacing existing saved reviews. Live PostgreSQL checks require a disposable
`POSTGRES_TEST_URL`; their repository coverage includes annotation writes, retries,
progress and export, but they remain skipped on this host.
