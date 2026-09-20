# Review Tag Generator API v1

Contract version: `1.0`. The machine validated DTOs live in `backend/app/contracts/models.py`; synthetic, model validated payloads live in `tests/fixtures/api/examples.json`. OpenAPI `info` must expose `contract_version: 1.0` when B01 exports the live API schema. This document freezes the payload shapes for backend and frontend agents. All JSON objects reject unknown request fields. IDs are canonical UUID strings. Timestamps are timezone-aware ISO-8601 values emitted in UTC.

`pipeline_version` and `aggregate_version` are lowercase 64-character SHA-256 digests, following section 4 of the implementation plan. Fixture digests are synthetic placeholders. `ontology_version` and `context_policy` are nonempty identifiers defined by their respective model tasks.

## Fixed labels, offsets and text

- Sentiment IDs: `negative=0`, `neutral=1`, `positive=2`. BIO IDs: `O=0`, `B-ASP=1`, `I-ASP=2`. Strings on the wire are lowercase names.
- A review contains 1–10,000 Unicode code points and at least one non-whitespace character. The server preserves the original string, including whitespace and punctuation. `rating` is absent or a strict integer from 1 to 5. It is metadata only.
- `start_char` is inclusive; `end_char` is exclusive. They index Unicode code points in `analysis.review_text`. `review_text[start_char:end_char]` must equal `raw_aspect`. The actual sentiment context interval must contain the mention and stay inside that text. `offset_unit` is always `unicode_code_points`. JavaScript consumers must translate code point positions before slicing UTF-16 strings.
- Mention IDs are UUIDs. A known normalized aspect has a stable snake_case ID, display label and tag. An unknown aspect is still returned, with `method=unknown`, `is_unknown=true` and null canonical ID, label and tag. Semantic similarity is a separate score; it is never a probability.
- `aspect_confidence` and `sentiment_confidence` lie in `[0,1]`. `confidence` is their minimum, an uncalibrated summary. The three unrounded sentiment probabilities lie in `[0,1]` and sum to 1 within `1e-5`; `sentiment_confidence` equals the selected sentiment probability within `1e-5`. Round only in presentation. Neutral tags describe a neutral observation and must not claim mixed opinion.
- `analysis.review_text` must exactly equal the submitted source string. The API calls `validate_original_text` against its persisted/preview input before returning it. `backend` is `transformer` in real service responses; `fake` is reserved for explicitly injected tests. No silent fallback is represented by this contract.

## Review session and endpoints

The user opens a product review page, optionally previews an ephemeral analysis, and submits a review. Preview never updates product totals. Submission persists the exact original text and queues fresh analysis. The worker runs extraction, sentiment, normalization and tag templates, stores one compatible run, and publishes an aggregate snapshot before marking the submission job complete.

| Method and path | Input | Success | Errors |
|---|---|---|---|
| `GET /health` | none | `200 Health` | process failure only |
| `GET /ready` | none | `200 Ready` after DB and compatible worker/model heartbeat | `503` |
| `POST /api/reviews/analyze` | `PreviewRequest` JSON: `product_id`, `review_text`, `rating?` | `202 PreviewQueued` with `preview_id`, `status_url`, `expires_at` | `404,422,429,503` |
| `GET /api/previews/{id}` | UUID path | `200 PreviewResult`: `queued`, `running`, `completed` with `analysis`, or `failed` with safe `error` | `404,410` |
| `POST /api/products/{id}/reviews` | `SubmitReviewsRequest` JSON: `reviews[1..100]`, each `review_text`, `rating?`, `source=manual`; `Idempotency-Key` UUID header | `202 JobAccepted` with `job_id`, `review_ids`, `duplicate_count` | `404,409,413,422,429,503` |
| `POST /api/products/{id}/reviews/import` | CSV/JSON multipart `file`; `Idempotency-Key` UUID header | `202 JobAccepted` (`review_ids=[]` until processing) | `404,409,413,415,422,429,503` |
| `POST /api/products/{id}/generate-tags` | `Idempotency-Key` UUID header; no body | `202 JobAccepted` (`review_ids=[]`) | `404,409,429,503` |
| `GET /api/products` | `page=1`, `page_size=20`, `search?` | `200 ProductPage` with `items`, `total`, `page`, `page_size` | `422` |
| `GET /api/products/{id}/insights` | UUID path | `200 ProductInsights` | `404` |
| `GET /api/products/{id}/tags` | `top_k=10` | `200 ProductTags` with snapshot metadata and supported ranked tags | `404,422` |
| `GET /api/products/{id}/reviews` | `page=1`, `page_size=20`, `aspect_id?`, `sentiment?` | `200 ReviewPage` with original text and latest compatible analysis/status | `404,422` |
| `GET /api/reviews/{id}` | UUID path | `200 ReviewDetail` | `404` |
| `GET /api/jobs/{id}` | UUID path | `200 Job` | `404` |
| `POST /api/jobs/{id}/retry` | `Idempotency-Key` UUID header | `202 JobAccepted` with new linked job ID | `404,409,429,503` |
| `GET /api/models/metrics` | none | `200 ModelMetrics`, with separate `historical` and `current` protocol records | `503` if evidence unavailable |

All path IDs are UUIDs. Invalid IDs, pagination or filters return `422 VALIDATION_ERROR`. Page size range is `1..100`; top K range is `1..50`. Upload limit is 10,485,760 bytes and 5,000 rows. Those bounds and the text bound match the C01 settings defaults; any configured lower limit is applied by endpoint validation. `Idempotency-Key` must be a canonical UUID. An identical retry gets the same stored response and IDs; reusing the key with a changed request yields `409`.

## Response models

`Analysis` includes original `review_text`, `mentions[]`, `backend`, `pipeline_version`, `model_hashes` (`aspect_extractor` and `sentiment_classifier` SHA-256), `ontology_version`, `context_policy`, `elapsed_ms`, `warnings[]` and `offset_unit`. Each mention has the original span, normalization, sentiment, probabilities, tag and actual context interval. The synthetic full response in `preview_success` demonstrates a positive Display and negative Battery from one review; `preview_no_aspect` returns an empty array without inventing a tag.

`Job` includes `job_id`, `type` (`review_submission`, `import`, `regeneration`), `status` (`queued`, `running`, `completed`, `completed_with_errors`, `failed`), `stage`, `attempt`, six row counts, safe nullable error code/summary, UTC creation/update times and nullable result URL. For imports, `total_rows = accepted_rows + rejected_rows + duplicate_rows`; pending accepted rows are `accepted_rows - completed_rows - failed_rows`. `completed` cannot contain rejected or failed rows; use `completed_with_errors`. A terminal retry creates a new linked job and never reopens the terminal record.

`ProductInsights` has `product`, nullable `snapshot_id`, `pipeline_version`, `aggregate_version`, `data_revision`, `stale`, nullable `generated_at`, review counts, sentiment distribution, `aspects[]`, classification lists and `representative_reviews[]`. Each aspect carries `counts` and `ratios` for all three sentiments, `mention_count`, `review_count`, `average_confidence`, `score`, nullable `aggregate_tag`, `classification` and `rank`. Counts represent distinct review-aspect votes; `mention_count` can be higher. Sentiment distribution counts these votes, never star ratings. Ratios are fractions in `[0,1]`, including explicit zeros. The classification lists partition the aspect IDs. Representatives group by aspect ID and sentiment, with review ID, excerpt, mention IDs and confidence; clients fetch full text from the review detail endpoint. Unknown mentions stay on review results but are excluded from canonical product tags.

For v1, the product sentiment distribution covers canonical review-aspect votes only. Unknown mentions remain visible in individual analysis results and do not contribute to canonical aspect counts. The aggregator task should verify this interpretation against the agreed ontology and record any contract change before consuming it.

An empty product has no snapshot (`snapshot_id` and `generated_at` null), zero counts and empty arrays. A stale response keeps the last published snapshot's revision, denominator and generated time; `stale=true` means a newer product revision is being aggregated. The server never mixes partly refreshed counts with that snapshot. `ProductTags` carries the same snapshot identity and revision, plus ranked supported strength/weakness/mixed tags. Insufficient evidence does not become a product tag.

`Product` includes UUID `product_id`, `source`, nullable `external_product_id`, `name`, `category`, nullable `brand` and UTC `created_at`. `ReviewDetail` includes the saved original text and optional rating, source, status, latest compatible analysis and submission time. `ReviewCounts.no_aspect` is a subset of analyzed reviews.

## Errors and retry behavior

Every non-2xx response uses `{ "error": { "code": ..., "message": ..., "details": [], "retryable": ... }, "request_id": "<uuid>" }`. `details[]` contains safe `{field?, message}` objects. Normalize FastAPI/Pydantic validation errors into this shape; never return raw exceptions or stack traces. Allowed codes are `VALIDATION_ERROR`, `NOT_FOUND`, `PREVIEW_EXPIRED`, `IDEMPOTENCY_CONFLICT`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `QUEUE_FULL`, `MODEL_UNAVAILABLE`, `DATABASE_UNAVAILABLE`, `ANALYSIS_FAILED`, `INTERNAL_ERROR`. The fixture has one payload for each code.

`429 QUEUE_FULL` supplies a `Retry-After` header. `503 MODEL_UNAVAILABLE` at enqueue means preserve the unsent draft. A saved review whose analysis later fails remains stored and is retried through its job. An expired preview returns `410` until purged, then `404`. Preview results for obsolete edited text must be discarded by the UI.

## Legacy core adapter

The framework-independent core keeps `ReviewAnalyzer.analyze()` and `TagResult` unchanged. `tag_result_from_mention` projects a validated HTTP mention onto a legacy `TagResult` for existing consumers. That projection deliberately drops probabilities and context; new API consumers use `Mention` directly. There is no reverse adapter because legacy results lack the evidence needed to construct a truthful `Mention`.
