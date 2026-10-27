# Current API reference

This page describes routes implemented in `backend/app/main.py`. Inspect the
running schema at `/docs` or `/openapi.json` for request validation and response
details. The [API v1 design contract](contracts/api-v1.md) is a target DTO/fixture
reference and has different routes and payloads.

Default API origin: `http://127.0.0.1:8000`. With the alternate local setup use
port 8011; through Compose use port 8080. The frontend proxies `/api/...` to its
configured API target. All paths below include the `/api` prefix.

## Health, products, and processing

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Database health, backend, context policy, worker heartbeat |
| GET | `/api/ready` | Ready only when a compatible worker heartbeat exists |
| GET / POST | `/api/demo/products` | List products / create with `{"name":"…"}` |
| GET | `/api/demo/products/{product_id}` | Published model evidence and insights |
| POST | `/api/demo/products/{product_id}/preview` | Queue expiring unsaved review previews |
| POST | `/api/demo/products/{product_id}/preview-summary` | Summarize completed, unexpired previews without saving |
| GET | `/api/demo/previews/{preview_id}` | Poll one preview |
| POST | `/api/demo/products/{product_id}/reviews` | Save reviews and queue analysis |
| POST | `/api/demo/products/{product_id}/jobs` | Alias for the review-submission route |
| POST | `/api/demo/imports/validate` | Validate file content without saving |
| POST | `/api/demo/products/{product_id}/imports` | Save accepted file rows and queue processing |
| POST | `/api/demo/products/{product_id}/regenerate` | Queue analyses for the active pipeline |
| GET | `/api/demo/jobs/{job_id}` | Poll durable job progress |
| POST | `/api/demo/jobs/{job_id}/retry` | Retry failed work without reposting source reviews |
| GET | `/api/demo/jobs/{job_id}/errors.csv` | Download complete row-error information |
| GET | `/api/models/metrics` | Recorded component evaluations and normalization gate |

Review preview and submission accept:

```json
{"reviews": ["Amazing display but terrible battery."]}
```

Preview returns queued IDs, not immediate analyses. Poll each ID until completed
or failed. Previews expire after 30 minutes and never change product totals.
Submission returns a 202 job; poll it before expecting a newly published snapshot.
Use an `Idempotency-Key` header for retryable review/import submissions.

For an unsaved shopping summary, send `{"preview_ids":["<preview UUID>","<preview UUID>"]}`
to the product's `preview-summary` route after polling completes. It accepts 1–100
IDs and returns `saved: false`, the pipeline version, duplicate-text count, and
`insights` using the same aggregation rules as saved products. IDs must belong to
that product, be complete and unexpired, and use the current pipeline. Repeated
IDs and whitespace/case-folded duplicate texts cannot inflate review support.
The endpoint publishes no snapshot and changes no saved review totals.

File validation/import uses JSON content rather than the target contract's
multipart upload:

```json
{"filename": "reviews.txt", "content": "Great display.\nPoor battery."}
```

Reviews must be nonblank and no longer than 10,000 Unicode code points. Inline
review requests contain 1–100 strings. Imports accept TXT/CSV/JSON/JSONL/NDJSON,
up to 10 MiB and 5,000 rows. See [getting started](getting-started.md#import-files).

## Evidence tools and optional assistance

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/demo/products/{product_id}/evidence-audit` | Single-review-removal robustness |
| GET | `/api/demo/products/{product_id}/quality-queue` | Advisory prediction review queue |
| GET | `/api/demo/products/{product_id}/compare/{other_product_id}` | Support-aware comparison |
| GET | `/api/assist/status` | Provider/model configuration status, without secrets |
| POST | `/api/assist/normalize` | Ephemeral exact-span mapping suggestion |
| POST | `/api/demo/products/{product_id}/ask` | Cited answer from published review excerpts |

The standalone suggestion accepts `review_text`, `raw_aspect`, `start_char`, and
`end_char`. Product questions use `{"question":"What do reviewers say about the battery?"}`.
Requests run only on demand. See [provider setup and validation](llm-assistance.md).

## Reviewer corrections

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/corrections/options` | Current canonical IDs and labels |
| POST | `/api/demo/products/{product_id}/corrections/suggest` | Record a server-generated suggestion for saved evidence |
| GET | `/api/demo/products/{product_id}/corrections/history` | Span-level decision history |
| POST | `/api/demo/products/{product_id}/corrections` | Append an accept/edit/reject decision |
| GET | `/api/demo/products/{product_id}/corrections` | Export the product's decision log |

Saved references include `snapshot_id`, `review_id`, `start_char`, and `end_char`.
Decision writes require `request_id`, reviewer, reason, and decision, with the
expected previous ID. Accept/reject reference a persisted `suggestion_id`;
supported edits provide explicit `canonical_id` (null for unknown) and sentiment.
See [complete correction semantics](review-corrections.md).

## Full-review annotations

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/demo/products/{product_id}/annotations` | Worklist and complete progress counts |
| GET | `/api/demo/products/{product_id}/annotations/{review_id}` | Draft, original predictions, and history |
| POST | `/api/demo/products/{product_id}/annotations` | Append a draft, reviewed, or adjudication revision |
| GET | `/api/demo/products/{product_id}/annotations/export` | Latest saved annotations in a published snapshot |

Worklist status values are `all`, `needs_review`, `reviewed`, and
`needs_adjudication`. Detail/export require `snapshot_id`; passing it to the
worklist also checks snapshot identity. An annotation contains explicit spans,
categories and sentiment plus reviewer/notes and expected annotation/correction
revision IDs. Empty completed reviews require `confirmed_no_aspects: true`.
See [the annotation guide](review-annotations.md) for editing and concurrency rules.

## Saved-data controls

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/demo/products/{product_id}/imports` | List saved import batches |
| DELETE | `/api/demo/products/{product_id}/imports/{job_id}` | Remove that batch's inserted reviews |
| DELETE | `/api/demo/products/{product_id}/saved-data` | Clear reviews but retain product |
| DELETE | `/api/demo/products/{product_id}` | Delete product and saved content |

Deletion cascades reviewer records for deleted analyses. Annotations on surviving
reviews remain. Active work blocks removals. See [saved-data behavior](saved-data.md).

## Shared behavior and boundaries

- Review/span offsets index the unchanged source in Unicode code points, with an
  inclusive start and exclusive end. Browser consumers must convert UTF-16 indices.
- Model evidence and totals come from a published snapshot. Reviewer records do
  not replace those predictions or automatically retrain the pipeline.
- UUIDs identify saved records. The local `demo-laptop` product alias is accepted
  where a product path is expected; do not assume it exists after deletion.
- Errors generally use FastAPI's `detail` field, not the target contract's error
  envelope. Common codes are 404 (missing record), 409 (conflict/stale revision),
  422 (invalid input), 429 (capacity/busy), 502 (invalid generated evidence), and
  503 (unavailable dependency). Inspect OpenAPI and the feature guide for details.
- The API is a local, unauthenticated application; product association is a
  consistency boundary, not authenticated multi-tenant authorization.
