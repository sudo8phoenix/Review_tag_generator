# Review corrections

Saved review evidence supports an explicit reviewer decision workflow. Open a
product's insights, then select a highlighted aspect or a prediction in the
review quality queue. The evidence drawer shows the original model result and a
**Review this prediction** section.

1. For an unknown aspect, optionally choose **Suggest mapping**. The server
   records its validated suggestion against that exact saved span.
2. Enter a reviewer name and a reason.
3. Choose **Accept suggestion**, **Reject suggestion**, or set the aspect and
   sentiment yourself and choose **Save correction**. To reject an extracted
   phrase as an aspect, check **This phrase is not a supported aspect** and save.
4. Reopen the drawer to see history. Choose **Export review decisions** below
   the quality queue to download the product's decision log.

Manual corrections work without an LLM provider. Unsaved preview evidence still
offers ephemeral suggestions; durable decisions require a saved analysis.

For complete-review progress, missing aspects and span edits, use the
[annotation workspace](review-annotations.md). New aspect decisions reopen a
previously completed review so annotation progress cannot silently become stale.

## Decision meanings

- **Accepted:** preserve the exact server-recorded mapping suggestion and the
  original predicted sentiment. Accepting a proposed new category records that
  proposal; it does not add the category to the ontology.
- **Edited:** record the reviewer's explicit canonical ID (or unknown), sentiment,
  and whether the span is a supported aspect. An edit may reference a suggestion
  or be entirely manual.
- **Rejected:** record that the suggestion was rejected. It creates no replacement
  mapping or sentiment. Rejecting a suggestion differs from rejecting an
  extracted phrase as an aspect.

Every decision is a new event. Earlier events remain in history. Original
analyses, evidence, aggregate votes, model scores and product snapshots are not
modified. No retraining or alias changes run automatically. History follows
the same analysis run when a later snapshot includes it; a different pipeline
version has its own history. Export includes historical decisions across the
product's saved analysis runs, with their pipeline versions and source text.

## Provenance and conflicts

Events include review/analysis IDs, exact source span, original prediction,
review-text hash, pipeline and ontology versions, snapshot ID, reviewer name,
reason, time, previous event ID, and optional provider/model and suggestion
payload. The browser references server-recorded suggestions rather than supplying
claimed provider responses.

Reviewer names are self-reported in this local app, rather than authenticated
identities. Exports are review decisions, not independently adjudicated gold
labels. Keep automated proposals and human-reviewed decisions distinct in later
evaluations.

Writes lock the owning product and require the referenced snapshot to remain
published and include the analysis. A snapshot change returns HTTP 409. Decisions
also include `expected_previous_id`, so concurrent decisions require reloading
history before saving. Retries with an unchanged `request_id` and identical body
return the saved event; changed bodies with the same ID return HTTP 409. The UI
preserves input and retains request IDs for unchanged retries.

Clearing reviews, deleting a product, or removing a batch cascades removal of
decisions and suggestions for deleted analyses. Decisions on surviving reviews
remain. Snapshot IDs are provenance identifiers: deleting an old snapshot alone
does not delete decisions on surviving reviews.

## API and persistence

| Endpoint | Purpose |
|---|---|
| `GET /api/corrections/options` | Current canonical IDs and labels |
| `POST /api/demo/products/{id}/corrections/suggest` | Generate and record a suggestion for saved evidence |
| `GET /api/demo/products/{id}/corrections/history` | History for a review span in a published snapshot |
| `POST /api/demo/products/{id}/corrections` | Append a reviewer decision |
| `GET /api/demo/products/{id}/corrections` | Export product decisions |

Span references use `snapshot_id`, `review_id`, `start_char`, and `end_char`.
Offsets index Unicode code points with an exclusive end. Decision POSTs also
require UUID `request_id`, `decision`, `reviewer`, and `reason`. Supply
`expected_previous_id` from history, or null for the first event. Accept/reject
require `suggestion_id`. A supported edit requires `canonical_id` (explicit null
means unknown) and `sentiment`. An unsupported edit uses `supported: false`,
`canonical_id: null`, and `sentiment: null`.

PostgreSQL deployments need `alembic upgrade head` through migration
`0004_review_corrections`. Local SQLite startup creates the two new tables
without replacing existing records. API and worker should use the same source
checkout and database configuration.

## Verification

HTTP/SQLite tests cover accepted, edited and rejected decisions, reopening,
idempotent retries, changed-request and concurrent-head conflicts, stale snapshots,
cross-product/span rejection, provider provenance, unknown versus unsupported
mentions, Unicode offsets, new-category suggestions, abstention, removal cleanup
and unchanged model snapshots.

Browser checks cover accept/edit/reject and export with explicitly injected
provider responses, save-failure recovery, history reload, and a real
browser-to-API-to-database correction using the heuristic test backend. Drawers
were checked at 320, 768 and 1440 pixels. PostgreSQL migration SQL generates through
0004; live PostgreSQL checks require `POSTGRES_TEST_URL` and remain skipped here.
