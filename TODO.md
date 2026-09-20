# Review Tag Generator — executable implementation TODO

Status: implementation in progress, based on inspected source and local evidence on 2026-09-20.
Audience: integration lead and small implementation agents.
Scope: laptop/electronics review analysis, product insights, Amazon demonstration.
This file replaces the older generic TODO.md. Review_Tag_Generator_TODO.md remains the historical task ledger.
Both TODO files remain ignored by Git at the user's request. Do not force-add or publish them.
Task markers below track implementation and verification, not merely specification.

## 1. Honest starting point

| Capability | Observed state | Remaining requirement |
|---|---|---|
| DistilBERT aspect checkpoint | Local; directory hash matched supplied Kaggle manifest | Strict startup verification and reproducible evaluation |
| DistilBERT sentiment checkpoint | Local; directory hash matched supplied Kaggle manifest | Same; check reload behavior and contextual sentiment |
| Historical A2 result | Exact-span F1 0.7061790668348045 | Preserve historical evidence; do not relabel as current pipeline evaluation |
| Historical A3 result | Macro F1 0.7495626626471136 | Applies to original full-review/aspect test protocol |
| Current review pipeline | Python prototype, real checkpoints load | Service lifecycle, limits, explicit backend, richer output |
| Clause-local sentiment | Added after full-sentence example failed | Validate on validation data; changes inference behavior; not covered by historical A3 |
| Normalization | 12 canonical labels; aliases plus token overlap | Full ontology, unknown handling, evaluated MiniLM fallback |
| Tags | Generic Great/Mixed/Poor wording | Neutral is not mixed; aspect-specific templates |
| Aggregation | Raw mention counts and first matching reviews | Deduplication, support thresholds, ranking, transactional persistence |
| Tests | Three tests using environment-dependent auto backend | Separate deterministic tests, integration checks, real-model evaluation |
| Amazon Reviews 2023 | Not present in inspected workspace | Bounded acquisition, provenance and batch demonstration |
| Backend/database/frontend | Not implemented | Tasks below |
| GitHub | main exists; source pushed previously | Future code pushes only in authorized workflow; never add local assets |

Known issues to turn into explicit tasks:
- ReviewAnalyzer(use_transformer=True) can still fall back if either checkpoint path is missing.
- Auto mode catches RuntimeError and can hide a broken model as a heuristic result.
- Extraction truncates at 256 tokens, silently discarding the remainder.
- Sentiment truncation can discard the aspect's surrounding context.
- aspect_context uses review.find(clause); repeated clauses can resolve to the wrong occurrence.
- Clause splitting can break negation/discourse meaning; an example passing does not establish correctness.
- Fallback has a NEGATIONS set but does not use it.
- Rule extraction can double-count overlapping aliases such as battery and battery life.
- ReviewAnalyzer.aggregate performs inference again rather than aggregating persisted predictions.
- Raw confidence/probabilities and normalization method are discarded from the combined response.
- The exported A3 confusion-matrix labels say positive/neutral/negative, but the notebook computes
  rows/columns in ID order negative/neutral/positive. Preserve original evidence and add a corrected derivative.
- A3 error-samples.jsonl currently contains a summary, not actual per-example classification errors.
- Dependency versions are unpinned; no reproducible project package/setup exists.
- README and winning-run action_required contain outdated statements; reconcile only against verified work.

## 2. Fixed MVP decisions — agents must not redesign these

1. Python 3.11; FastAPI + Pydantic v2; SQLAlchemy 2 + Alembic; PostgreSQL.
2. React + TypeScript + Vite; Tailwind CSS; Recharts; React Router; TanStack Query.
   Frontend foundation agent selects mutually compatible current stable versions and commits its lockfile.
3. One application codebase with an API process and a worker process; PostgreSQL is the only persistent store.
   No Redis, Celery, Kafka, microservices, external LLM calls, or training from HTTP requests.
4. The worker owns one loaded model bundle and one inference semaphore. API never loads duplicate models.
   Live preview has priority over bulk work; bulk work yields after each review.
5. API binds to 127.0.0.1 by default; this is a local demo until authentication/authorization is implemented.
   Public hosting is a separate task after this plan; do not expose anonymous review writes publicly.
6. Inference uses the existing saved weights; no automatic retraining or replacing them with base models.
7. Preview is ephemeral and never changes product totals. Submit stores the review and schedules analysis.
8. Submitted original text is retained exactly. Offsets reference that exact text.
9. Aggregates use only successful analyses for the currently active pipeline version.
10. Unknown aspects stay visible in individual review results; exclude them from canonical product tags.
11. Rating is optional input metadata, not an aspect sentiment label and not a sentiment override.
12. Amazon is for inference/demo only. No gold sentiment is inferred from star ratings.
13. Keep models, datasets, raw review output and downloaded archives outside Git, consistent with .gitignore.
14. No fake production responses or silent rule fallback. Test fakes require explicit dependency injection.
15. This checklist refines the source build plan. Clarifications here own session semantics and API v1;
    do not rename or fork interfaces independently. Proposed defaults below must be coded centrally.

## 3. How a review session works

A session means one user reviewing one product in the browser; it is not a chat and does not train the model.

1. Open /products/:productId/review. Fetch product metadata; unknown product shows 404.
2. User enters English review text (1–10,000 Unicode code points after checking nonblank content)
   and optional integer rating 1–5. UI stores draft in sessionStorage, scoped by product ID.
3. Click "Preview tags". UI sends POST /api/reviews/analyze with product_id, review_text, rating.
4. API validates input, assigns a UUID preview_id, queues an ephemeral analysis job, returns 202.
5. UI polls GET /api/previews/:previewId every 1 second, increasing to 3 seconds after 15 seconds.
6. Worker loads models once at startup, then executes:
   original review -> overlapping extraction windows -> original character spans ->
   aspect-conditioned sentiment -> normalization -> deterministic tag templates.
7. UI renders original text with highlights, positive/neutral/negative labels, tags, and confidence.
   No aspects means "No supported product features detected"; never fabricate a tag.
8. Editing text or rating invalidates the visible preview. Late results for old text never replace new state.
9. Click "Submit review", with or without a completed preview. Send POST /api/products/:id/reviews
   with one review, source=manual, and a per-submission Idempotency-Key UUID.
10. Server validates again, persists the review and job in one DB transaction, returns 202 + job_id.
    MVP does not reuse preview predictions on save: worker reanalyzes the saved source of truth.
11. UI clears sessionStorage only after save is acknowledged. Analysis can finish afterward.
12. Worker stores an immutable analysis run + mentions, updates product data revision, then schedules
    an aggregate refresh. Submission is completed only after its relevant aggregate snapshot is published.
13. UI polls job status, invalidates product queries on completion, and offers "View product insights".
14. Refreshing the page preserves the saved job_id; GET job state restores progress.
15. Model unavailability does not erase a draft or create fake results. Show retry guidance.
    Once a review is saved, retries resume its job; do not post a new copy.

Failure-state behavior:
| Event | Required user behavior |
|---|---|
| Blank/oversized input | Inline error before request and HTTP 422 if sent directly |
| Model unavailable at enqueue | HTTP 503; preserve draft; allow retry |
| Server queue full | HTTP 429 + Retry-After; preserve input |
| Lost response after save | Retry same Idempotency-Key + identical body; return same job/review IDs |
| Same key, changed request | HTTP 409; ask client to create a new submission key |
| Analysis fails after save | Review remains saved with failed state; show job failure and retry |
| Preview expires | HTTP 410 until cleanup removes it; then 404; client can create a new preview |
| Old preview returns after edit | Discard it; no tag/text mismatch |
| Aggregate currently stale | Show last complete snapshot plus "Updating"; no partial new totals |

## 4. Repository boundaries and shared configuration

Target layout (new directories are implementation tasks, not already present):

- src/review_tag_generator/: framework-independent models, ontology, normalization, tags, aggregation.
- backend/app/: config.py, main.py, contracts/, api/, db/, repositories/, services/, worker/.
- backend/alembic/: migration scripts; backend/alembic.ini.
- frontend/src/: api/, components/, features/review/, features/products/, features/upload/,
  features/metrics/, routes/, styles/, test/.
- scripts/: verify_artifacts.py, evaluate_pipeline.py, sample_amazon.py, run_batch.py,
  export_openapi.py, seed_demo.py.
- tests/unit/, tests/integration/, tests/model/, tests/fixtures/.
- docs/contracts/, docs/architecture.md, docs/operations.md, docs/evaluation.md.
- audit/evidence/current/: derived verified metrics, benchmark results, no raw customer reviews.
- data/: ignored datasets, annotation/evaluation sets, batch output, temporary imports.
- models/: ignored weights and optional MiniLM snapshot.
- contracts/openapi.json: versioned API contract, generated by backend.
- .github/workflows/: CI; compose.yaml; .env.example; pyproject.toml and dependency lockfiles.

Central defaults owned by C01/C02:
- MODEL_BACKEND=transformer; MODEL_DEVICE=cpu; MAX_MODEL_TOKENS=256;
  EXTRACTION_STRIDE=64; MAX_REVIEW_CHARS=10000; MAX_REVIEW_TOKENS=4096.
- MAX_UPLOAD_BYTES=10485760; MAX_UPLOAD_ROWS=5000; MAX_INLINE_REVIEWS=100.
- PREVIEW_TTL_SECONDS=1800; QUEUE_CAPACITY=100; JOB_MAX_ATTEMPTS=3.
- WORKER_LEASE_SECONDS=120; WORKER_HEARTBEAT_SECONDS=10; INFERENCE_TIMEOUT_SECONDS=60.
- MIN_REVIEW_SUPPORT=3; REPRESENTATIVES_PER_SENTIMENT=3; DEFAULT_TOP_K=10; MAX_TOP_K=50.
- PAGE_SIZE=20; MAX_PAGE_SIZE=100; CORS_ORIGINS=http://localhost:5173.
- Paths resolve from configuration, never a developer's absolute directory.
- Pipeline version = SHA-256 of canonical JSON containing both checkpoint hashes, tokenizer hashes,
  ontology version, normalization snapshot/revision/threshold, context policy, window settings,
  BIO decoder policy, tag templates, and relevant runtime versions.
- Aggregate version also includes aggregation thresholds/formula version.
- Similarity threshold must be calibrated by M05; no unvalidated numeric default promoted to release.

## 5. Shared data and API contracts

C02 creates Pydantic models, synthetic JSON examples and schema docs before consumers implement them.
Use UUIDs for internal IDs; timestamps UTC ISO-8601 strings; extra request fields rejected.
Preserve negative=0, neutral=1, positive=2 and O=0, B-ASP=1, I-ASP=2.

Mention:
- mention_id, raw_aspect, start_char, end_char, aspect_confidence.
- normalized_aspect_id: stable snake_case ID or null; normalized_aspect: display label or null.
- normalization: {method: alias|semantic|unknown, similarity: number|null, is_unknown: boolean}.
- sentiment: positive|neutral|negative; sentiment_confidence.
- probabilities: {negative, neutral, positive}; values [0,1], sum within 1e-5 of 1 before display rounding.
- tag: string|null; unknown aspect has null tag; neutral template must not imply mixed opinions.
- confidence: min(aspect_confidence, sentiment_confidence), explicitly an uncalibrated summary score.
- context_start_char, context_end_char: actual original-text interval used for sentiment.
- Never use semantic similarity as a probability.

Analysis:
- review_text, mentions[], backend, pipeline_version, model_hashes, ontology_version,
  context_policy, elapsed_ms, warnings[], offset_unit="unicode_code_points".
- Returned source text must exactly equal submitted text.
- Compatibility adapter preserves existing analyze()/TagResult callers while HTTP uses the new DTO.

Job:
- job_id, type (review_submission|import|regeneration), status
  (queued|running|completed|completed_with_errors|failed), stage, attempt.
- total_rows, accepted_rows, rejected_rows, duplicate_rows, completed_rows, failed_rows,
  error_code|null, error_summary|null, created_at, updated_at, result_url|null.
- For imports: total_rows = accepted_rows + rejected_rows + duplicate_rows;
  accepted_rows = completed_rows + failed_rows + pending_rows.
- Completed never means 100% successful when failed/rejected counts are nonzero.
- Terminal jobs never automatically go back to running; retry creates a new linked job.

Product:
- product_id, source, external_product_id|null, name, category, brand|null, created_at.
- Product seed/import only for MVP; no public product-management screen.

Product insights:
- product, snapshot_id|null, pipeline_version, aggregate_version, data_revision,
  stale, generated_at|null, review_counts {total, analyzed, pending, failed, no_aspect}.
- sentiment_distribution {positive, neutral, negative}: counts of review-aspect votes, not ratings.
- aspects[]: aspect_id, label, counts, ratios, mention_count, review_count,
  average_confidence, score, aggregate_tag, classification, rank.
- strengths[], weaknesses[], mixed[], insufficient_evidence[]: references to aspect IDs.
- representative_reviews per aspect/sentiment: review_id, excerpt/full review via detail endpoint,
  mention IDs and confidence; evidence must match stored analyzed text.
- Include all sentiment keys even when zero. Ratios [0,1]; UI converts to percentages.
- Every response from one snapshot uses the same revision and denominator.

API v1 (retain /api prefix from source plan; contract_version in OpenAPI info):
| Method/path | Input | Success | Errors |
|---|---|---|---|
| GET /health | none | 200 process alive | Only process failure |
| GET /ready | none | 200 DB + compatible worker/model heartbeat healthy | 503 |
| POST /api/reviews/analyze | review_text, product_id, rating? | 202 preview_id, status_url, expires_at | 404,422,429,503 |
| GET /api/previews/{id} | UUID | 200 status, analysis when complete, error when failed | 404,410 |
| POST /api/products/{id}/reviews | reviews[1..100], Idempotency-Key header | 202 job_id, review_ids, duplicate_count | 404,409,413,422,429,503 |
| POST /api/products/{id}/reviews/import | CSV/JSON multipart file, Idempotency-Key | 202 job_id | 404,409,413,415,422,429,503 |
| POST /api/products/{id}/generate-tags | Idempotency-Key | 202 job_id (aggregation only) | 404,409,429,503 |
| GET /api/products | page, page_size, search? | 200 items[], total, page, page_size | 422 |
| GET /api/products/{id}/insights | none | 200 ProductInsights | 404 |
| GET /api/products/{id}/tags | top_k=10 | 200 snapshot metadata + ranked supported tags | 404,422 |
| GET /api/products/{id}/reviews | page, page_size, aspect_id?, sentiment? | 200 items[], total | 404,422 |
| GET /api/reviews/{id} | UUID | 200 original review + latest compatible analysis/status | 404 |
| GET /api/jobs/{id} | UUID | 200 Job | 404 |
| POST /api/jobs/{id}/retry | Idempotency-Key | 202 new job_id for retryable failed rows | 404,409,429,503 |
| GET /api/models/metrics | none | 200 historical/current protocol-separated metrics | 503 if evidence unavailable |

Error envelope for every non-2xx:
{ "error": { "code": "MODEL_UNAVAILABLE", "message": "Analysis is temporarily unavailable.",
  "details": [], "retryable": true }, "request_id": "<uuid>" }
Allowed codes: VALIDATION_ERROR, NOT_FOUND, PREVIEW_EXPIRED, IDEMPOTENCY_CONFLICT,
PAYLOAD_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE, QUEUE_FULL, MODEL_UNAVAILABLE,
DATABASE_UNAVAILABLE, ANALYSIS_FAILED, INTERNAL_ERROR.
Normalize FastAPI validation errors into this envelope; never return raw exception text or stack traces.

## 6. Persistence and job semantics

C03 owns table definitions and migrations; C04 owns transactions and uniqueness enforcement.

Tables:
- products: UUID PK, source, external_product_id, name, category, brand, data_revision default 0.
  Unique (source, external_product_id) where external_product_id is not null.
- reviews: UUID PK, product_id FK, source, external_review_id nullable, review_text, text_sha256,
  dedup_key, rating nullable, helpful_votes >=0, submitted_at, analysis_status.
  Unique (product_id, dedup_key); manual dedup_key hashes exact text+rating; external data uses
  stable source+external review ID. Do not globally deduplicate identical text across products.
- analysis_runs: UUID PK, review_id FK, pipeline_version, original_text_sha256,
  backend, context_policy, elapsed_ms, created_at. Unique (review_id, pipeline_version).
  Contains only successful complete results; failed execution is represented by jobs/review status.
- aspect_mentions: UUID PK, analysis_run_id FK, raw_aspect, offsets, canonical ID/label,
  confidences, probabilities JSONB, normalization method/score, tag, context offsets.
  Unique (analysis_run_id, start_char, end_char); confidence/offset CHECK constraints.
- product_snapshots: UUID PK, product_id FK, pipeline_version, aggregate_version,
  data_revision, payload JSONB, created_at. Unique (product_id, aggregate_version, data_revision).
- products.current_snapshot_id: nullable FK to product_snapshots; replaced only after snapshot insert succeeds.
- processing_jobs: UUID PK, type, status, stage, pipeline_version, counts, parent_job_id nullable,
  attempt, leased_by, lease_expires_at, safe error fields, timestamps.
- job_items: PK(job_id, item_key), review_id nullable, status, attempt, safe error;
  durable row progress so retries do not duplicate successful results.
- idempotency_requests: endpoint_scope + key unique, request_sha256, response JSONB, job_id.
  The saved response and job/review insert commit together.
- analysis_previews: UUID PK, product_id, text, rating, status, analysis JSONB nullable,
  expires_at, lease data; excluded from product queries, purged after TTL.
- worker_status: worker_id PK, heartbeat, pipeline_version, model_health, busy; no raw error secrets.

Index reviews by product_id/submitted_at/id; mentions by canonical ID and analysis_run;
jobs by status/lease_expires_at/created_at; previews by status/expires_at.
Use DB transactions and SELECT FOR UPDATE SKIP LOCKED for claims; one compatible worker in MVP.
Database time defines lease expiry. Reclaim expired items only while attempts <3.
Inference occurs outside DB transactions; commit predictions atomically afterward with a lease-owner check.
Unique run/item constraints make at-least-once execution safe; stale worker writes must be rejected.
Every newly committed analysis increments product data_revision in the same transaction.
Aggregation captures a revision, computes one consistent DB snapshot, locks product on publish and
checks revision still matches. If changed, discard candidate and retry; never publish obsolete totals as current.
Review deletion is not exposed in MVP; document child cascades for internal maintenance only.

## 7. Agent execution rules

- Assign exactly one task ID per agent. Read sections 1–6, the task, and its completed dependency handoffs.
- Status markers: [ ] pending; [~] working; [x] implemented and checks passed; [!] blocked with evidence.
- All tasks below start pending. Existing prototype code is not an automatic pass.
- Own only listed paths. Shared-file changes go through their named owner/integration lead.
- Do not change contracts, thresholds, model weights, label IDs, or scope to make a test pass.
- Do not train, download whole datasets, publish, force-push, delete user artifacts or deploy as incidental work.
- Tests for storage use disposable PostgreSQL with a name ending _test; never the development/customer DB.
- New dependencies must be justified in handoff; use the shared lockfile owner to avoid simultaneous edits.
- A missing path named under "Owns" is created by that task. A required check not run is BLOCKED, not PASS.
- Fix failures inside the task; record unresolved ones and release only independent downstream work.
- No global git add . with ignored assets forced in; inspect changed/staged paths.
- The integration lead reviews each task before marking [x], merges sequentially, and checks dependent contracts.
- Agent names in this plan describe roles; they do not imply an agent has already run.

Required handoff:
Task ID / status / base commit or workspace snapshot
Files changed
Contract changes (normally none)
Exact commands + exit codes + artifact paths
Fixtures and model/dataset/pipeline versions
Acceptance checks passed/failed/not run
Remaining limitations and task IDs affected
Next task(s) ready

Required command conventions after C01/F01 exist:
- Core: .venv/bin/python -m pytest tests/unit
- Database/API: .venv/bin/python -m pytest tests/integration
- Model: .venv/bin/python -m pytest -m model tests/model
- Frontend: npm --prefix frontend run typecheck
  npm --prefix frontend run lint
  npm --prefix frontend run test -- --run
  npm --prefix frontend run build
- Browser: npm --prefix frontend run test:e2e
- Run only relevant paths during an individual task; run all gates at integration.
- Missing model assets may skip model tests in lightweight CI only; release gate must run them.

## 8. Foundation and model tasks

### [x] C01 — Reproducible Python project
Owner: foundation agent. Depends: none.
Owns: pyproject.toml, Python lockfile, requirements-inference.txt, .python-version,
.env.example, tests/conftest.py, backend/app/config.py.
Steps:
1. Package existing src/review_tag_generator without moving it. Require Python 3.11.
2. Define core, backend, evaluation and test dependency groups; freeze a tested dependency set.
3. Make python -m pytest find the installed package; remove ad hoc sys.path mutations from tests.
4. Add validated settings from section 4; use path values/names only in .env.example.
5. Set explicit profiles: unit fake, local transformer, release transformer.
6. Lock inference versions only after verifying compatibility with the transferred weights.
Checks: install into a fresh temporary venv; import package without loading models;
invalid config rejected; env overrides deterministic; no secret/artifact files tracked.
Done: one documented install command works; reproducible dependencies; unit tests never auto-load weights.
Handoff: environment versions, install command, settings contract; unblocks C02, M01, F01.

### [x] C02 — Freeze wire contracts and fixtures
Owner: contract agent. Depends: C01.
Owns: backend/app/contracts/, docs/contracts/api-v1.md, tests/fixtures/api/,
core schema adapters in src/review_tag_generator/schemas.py.
Steps:
1. Encode every section 5 DTO with validation and explicit enum/offset semantics.
2. Add aliases/compatibility adapters for existing TagResult calls; HTTP uses new Mention.
3. Produce synthetic examples: preview queued/success/no-aspect/failed, job partial failure,
empty product, stale product, supported positive/negative/mixed aspect, all error envelopes.
4. Validate request lengths by Unicode code points; prohibit blank text; retain original text unchanged.
5. Define rating integer 1–5, product IDs UUID, confidence ranges, optional timestamp semantics.
Checks: JSON round trips; reject bad offsets/enums/rating/probability totals; fixture schema validation.
Done: all consumers use these contracts; no per-agent label maps or response shape inventions.
Handoff: contract version and examples; unblocks C03, M02, B01, F02.

### [x] M01 — Verify assets and fail closed on model startup
Owner: runtime agent. Depends: C01.
Owns: transformer_models.py loading, pipeline.py initialization, scripts/verify_artifacts.py,
tests/unit/test_model_loading.py, tests/model/test_checkpoint_reload.py.
Steps:
1. Configure both model paths; require config/tokenizer/weights before constructing a transformer backend.
2. Verify expected directory hashes using the notebook algorithm: sorted relative filenames + file bytes,
streamed into SHA-256. Do not hash a tar archive and compare that to a directory hash.
3. Use local_files_only=True; prohibit network fallback or loading unfine-tuned base weights.
4. Verify config label maps; collect missing/unexpected keys on load and fail for unexplained differences.
5. Investigate the prior LayerNorm beta/gamma warnings using saved tensor names and actual loader report.
Do not rewrite original checkpoints; any conversion is a new derived artifact with its own hash.
6. Make use_transformer=True fail on missing paths or dependencies. Restrict heuristic mode to explicit opt-in.
Auto mode cannot conceal model runtime/corruption errors; expose backend in every result.
7. Use eval(), inference_mode(), configurable device; no per-request model loading.
Checks: absent files, altered hash, wrong labels, unavailable dependencies, reload determinism;
repeat inference verifies single initialization; explicit fake works without weights.
Done: worker cannot become ready using fallback accidentally; original checkpoint hashes unchanged.

### [x] M02 — Windowed extraction and exact source offsets
Owner: extraction agent. Depends: C02, M01.
Owns: transformer_models.py extraction method, extraction.py, tests/unit/test_spans.py,
tests/model/test_long_reviews.py.
Steps:
1. Tokenize original text with overflow windows at max length 256 and stride 64.
Reject inputs exceeding 4096 total content tokens with a typed error; never silently drop tail text.
2. Retain global offsets, mask padding/specials, decode BIO consistently with documented orphan-I policy.
Baseline-compatible policy drops orphan I; track it as a diagnostic instead of inventing boundaries.
3. Resolve overlap duplicates by exact span; choose candidate farthest from a window boundary,
then higher confidence, then earlier window. For overlapping non-identical candidates use the same
ordering and keep a non-overlapping set; document seam limitations for long multiword aspects.
4. Remove nested alias matches in explicit heuristic mode by longest span, then earliest start.
5. Validate text[start:end] == raw_aspect for every result; sort by offsets; retain repeated occurrences.
Checks: emoji before aspect, repeated terms, punctuation, multiword, no aspects, window seams,
a feature after token 256, exact 4096-token boundary and over-limit rejection.
Done: coverage is complete within limits and all offsets reproduce original substrings.

### [x] M03 — Sentiment context policy and probabilities
Owner: sentiment agent. Depends: M02.
Owns: sentiment.py, transformer_models.py sentiment method, tests/unit/test_context.py,
tests/model/test_aspect_sentiment.py.
Steps:
1. Implement policies full_review and local_clause behind a named setting; log policy in result/version.
2. Replace review.find-based clause lookup with delimiter match positions; require whole aspect containment.
Handle repeated identical clauses, apostrophes, abbreviations and Unicode with explicit tests.
3. Preserve negation and modifiers. Do not globally split on "and"; test contrast, anaphora and shared opinions.
4. If a selected context exceeds pair token budget, choose a token window centered on the target occurrence,
including the complete aspect. Record resulting context boundaries.
5. Keep exact review/aspect pair order and label map from training. Return all unrounded probabilities.
6. Fix or explicitly document heuristic negation handling for demo-only mode; never present heuristic
scores as calibrated model probabilities.
7. Do not claim local_clause is superior until M04's validation comparison selects it.
Checks: original requested example, reverse contrast, neutral, "not good", "not bad",
repeated aspects with opposing opinions, no opinion, aspect at end of long review.
Done: configurable policy, correct boundaries, probability sum, deterministic pair construction.

### [~] M04 — Reproduce metrics and select context policy on validation only
Owner: evaluation agent. Depends: M03.
Owns: scripts/evaluate_pipeline.py, docs/evaluation.md, audit/evidence/current/,
tests/unit/test_metrics.py; original Kaggle evidence is read-only input.
Steps:
1. Verify processed split hashes using original serialized review/pair representation from the notebook,
not raw file SHA-256. Record both file hashes and original representation hashes with algorithm names.
2. Reproduce full-review/aspect sentiment baseline with unchanged weights and saved test pairs.
Compare confusion matrix, label order and precision/recall to historical metrics.
3. Compare full_review and local_clause on validation only; choose higher Macro F1 subject to all-class
recall >=0.50. Tie within 0.001 prefers full_review. Record decision before held-out evaluation.
4. Freeze policy/settings; run held-out test once for reporting. Do not retune on reported test failures.
5. Preserve historical A3 export and write corrected label-order derivative with provenance.
6. Export real sentiment error examples to ignored data/evaluation; publish only aggregate categories
and synthetic/redacted examples. Preserve A2's 597 original error entries.
7. If notebook preprocessing/decoding cannot be reproduced, document exact discrepancy and block parity claim.
Checks: metric arithmetic against hand-computed confusion matrix; repeat deterministic evaluation;
historical/current protocol labels visible; original hashes unchanged.
Done: current A2 exact-span F1 >=0.70; current A3 Macro F1 >=0.65, each recall >=0.50,
and improvement over baseline under matched splits, or an explicit blocking report.
Do not retrain under this task. A failing gate goes to lead with evidence.

### [x] M05 — Versioned ontology and semantic normalization
Owner: normalization agent. Depends: C02, M01.
Owns: ontology.py, normalization.py (new), ontology data, scripts/evaluate_normalization.py,
tests/unit/test_normalization.py.
Steps:
1. Define stable canonical IDs/display labels for Battery, Display, Performance, Processor, Keyboard,
Trackpad, Camera, Speakers, Storage, RAM, Build Quality, Weight, Design, Price, Value, Heating,
Charging, Ports, Delivery, Packaging, Customer Service.
2. Preserve requested aliases screen/display/monitor -> Display; battery/battery life -> Battery.
Keep Price distinct from Value and Processor distinct from overall Performance.
3. Reject duplicate alias ownership; do not map adjectives like "fast" into a feature without evidence.
Ambiguous "charge" remains unknown unless review context establishes Charging.
4. Normalize case/whitespace; match exact aliases first. For remaining terms use local
sentence-transformers/all-MiniLM-L6-v2 snapshot pinned to a resolved immutable revision.
Cache normalized alias/canonical embeddings once; cosine similarity, deterministic tie handling.
5. Create 200 labeled mapping examples: 100 development + 100 held-out, including unknowns;
split paraphrase families to avoid leakage. Human review is required before claiming gold accuracy.
6. Tune threshold on development set (candidate 0.50..0.90 step 0.02); highest accuracy wins,
ties prefer fewer false known mappings then higher threshold. Freeze before held-out run.
7. Return method, score and unknown flag; optional semantic module disabled is explicit alias-only version.
Checks: aliases, multiword, plurals, ambiguity, unrelated terms, threshold boundaries, collision detection.
Done: held-out normalization accuracy >=0.80 with unknowns included; per-class/unknown metrics reported.
If human labels are unavailable, implement/run fixtures but mark quality gate pending human review.

### [x] M06 — Customer-friendly deterministic templates
Owner: tags agent. Depends: M05.
Owns: tags.py, ontology template fields, tests/unit/test_tags.py.
Steps:
1. Define positive/negative/neutral templates for every canonical ID.
2. Required mention wording: Great Display, Poor Battery, Neutral Display Feedback.
3. Use aspect-specific phrasing: Low Weight/Heavy Build; Runs Cool/Overheats;
Good Value/Poor Value; Affordable Price/High Price, with neutral versions.
4. Unknown -> null tag plus visible "Unrecognized aspect" status in UI; do not invent a product feature.
5. Invalid sentiment or canonical ID fails validation; keep display wording separate from stable IDs.
Checks: full ontology x 3 labels; deterministic text; neutral never shown as Mixed.
Done: template coverage complete; source-plan illustrative tag variations documented, not silently divergent.

### [x] M07 — Deterministic product aggregation from saved analyses
Owner: aggregation agent. Depends: M06, C02.
Owns: aggregation.py, tests/unit/test_aggregation.py, docs/contracts/aggregation.md.
Steps:
1. Pure function consumes validated persisted analyses, never calls model inference.
2. Group by product/canonical ID. Track raw mention_count separately from distinct review_count.
3. Each review contributes one vote per canonical aspect: opposing positive and negative mentions ->
neutral vote plus contradictory_review_count; otherwise choose the non-neutral label if present,
else neutral. Vote confidence = minimum mention summary confidence within that review/aspect.
4. Counts and sentiment distribution use these deduplicated votes. Ratios divide by review_count.
5. Support <3 distinct reviews -> insufficient_evidence, excluded from top tags/strengths/weaknesses.
All supported votes neutral -> neutral classification. Otherwise positive >=0.80 excellent,
>=0.60 good; negative >=0.70 poor, >=0.50 weak; remaining -> mixed.
6. score = log1p(review_count) * average_vote_confidence * abs(positive_ratio-negative_ratio).
Use natural log; no helpfulness multiplier. Sort score descending, review_count descending,
canonical ID ascending. Assign 1-based rank to supported aspects.
7. Keep mixed/neutral aspects separate; never list a 50/50 aspect as both a strength and weakness.
8. For each aspect/sentiment choose at most 3 distinct supporting reviews: confidence descending,
helpful_votes descending, review_id ascending. Every selected mention must support its displayed label.
Contradictory neutral votes must be labeled "mixed within review", not quoted as a purely neutral mention.
9. Include all zero counters; handle empty products; retain enough unrounded values for reproducibility.
Checks: hand-calculated empty/all-neutral/50:50/boundary cases; repeated aliases; duplicate review inputs;
Top-K; stable ties; contradictory mentions; permutation invariance; exact representative membership.
Done: totals reconcile, no NaN, no inference calls, no double counting.
Contract clarification: source plan used raw mention_count in ranking; use review_count here to prevent
one repetitive review dominating. Preserve both fields and document this v1 refinement.

### [ ] M08 — Complete versioned analysis bundle
Owner: integration lead. Depends: M04, M06, M07.
Owns: pipeline.py composition, tests/model/test_pipeline_integration.py, model manifest derivative.
Steps:
1. Compose M02/M03/M05/M06 under one bundle; attach metadata, separate confidences and warnings.
2. Expose analyze_review, analyze_batch with bounded batch size, and aggregate_saved as separate calls.
3. Ensure warm startup runs a model health fixture; no-aspect is valid, not failure.
4. Keep existing API-compatible adapter; backend consumes v1 DTO.
5. Record hash/version and actual context policy; no claim that current score equals historical by default.
Checks: requested review returns Display positive/Battery negative; unknown/no-aspect/Unicode/long review;
same input stable; no unexpected model reload; original model directories unchanged.
Done: all model quality gates pass; otherwise downstream UI may use named fixtures but release remains blocked.

## 9. Backend and data tasks

### [~] C03 — PostgreSQL schema and migrations
Owner: database agent. Depends: C02.
Owns: backend/app/db/, backend/alembic/, backend/alembic.ini,
tests/integration/test_migrations.py.
Steps:
1. Implement section 6 tables, constraints and indexes; split circular product/snapshot FK into
a subsequent migration step. Store canonical IDs as text tied to ontology version, not DB enums.
2. Use SQLAlchemy sessions scoped to transaction; configure pool and statement timeout.
3. Support migration from empty DB and version upgrade. Never auto-create schema at every HTTP request.
4. Add synthetic product seed via scripts/seed_demo.py with stable external demo IDs.
5. Store timestamp/timezone and JSONB explicitly; numeric precision must retain probabilities.
Checks: disposable Postgres upgrade -> downgrade -> upgrade; duplicates/FKs/CHECKs;
rollback; unique nullable external IDs; concurrent duplicate insert; two products with identical review text.
Done: tests run on PostgreSQL, not SQLite as a substitute; schema matches DTO semantics.

### [ ] C04 — Repositories, idempotency and snapshot transactions
Owner: persistence agent. Depends: C03.
Owns: backend/app/repositories/, tests/integration/test_repositories.py.
Steps:
1. Implement product/review listing and filtered review detail with stable pagination order.
2. Implement ingest transaction: idempotency lookup, body hash conflict detection, review dedup,
job/item creation, saved response; identical concurrent requests resolve to one committed job.
3. Implement atomic successful analysis insert and product revision increment; no partial mentions.
4. Implement revision-safe snapshot publish using section 6 protocol.
5. Do not store/retrieve raw ORM objects as HTTP contracts; repositories return typed domain records.
6. Define failures (not found, duplicate, conflict, transient DB) for service mapping.
Checks: retry after lost response; same key/different body; concurrent commits;
same text/new rating; same external ID changed payload -> conflict; rollback at each write stage.
Done: totals unchanged by re-ingestion or failed transactions; no duplicate runs after retries.

### [ ] B01 — API shell, settings, validation and availability
Owner: API foundation agent. Depends: C02, C03.
Owns: backend/app/main.py, backend/app/api/health.py, error middleware, request limits,
tests/integration/test_api_foundation.py.
Steps:
1. Create FastAPI app factory and lifespan; DB pool only in API, models only in worker.
2. /health means process alive; /ready checks DB and a fresh compatible worker heartbeat.
3. Implement request UUID, error envelope, restricted CORS and body limits before body buffering.
4. Validate configured deployment profile; local binds loopback; no public mode without auth.
5. Reject malformed JSON, unsupported types, invalid pagination; never echo secrets/traceback.
6. Define OpenAPI responses from C02; place generated schema at contracts/openapi.json.
Checks: DB down, no worker, wrong pipeline worker, stale heartbeat, malformed/oversized/chunked body,
CORS preflight accepted/rejected; OpenAPI conforms to fixtures.
Done: health and readiness differ correctly; typed errors; no weights loaded in API process.

### [ ] B02 — Durable worker and bounded inference scheduling
Owner: worker agent. Depends: C04, M08, B01.
Owns: backend/app/worker/, tests/integration/test_worker.py.
Steps:
1. Startup verifies assets and loads one bundle. Publish healthy heartbeat only after warm inference succeeds.
2. Claim preview before bulk items; after five consecutive previews allow one bulk item to prevent starvation.
3. Execute a single inference at a time; health/heartbeat thread remains responsive.
4. Use DB leases/owner checks; renew every 10 seconds; after crash expired work can retry at most 3 times.
5. Persist item result atomically; classify transient retryable and permanent failures; mark terminal counters.
6. Supervise inference timeout: mark worker unhealthy and terminate/restart the worker process after 60s
of stuck inference, relying on leases for recovery. Do not claim Python thread cancellation stops PyTorch.
7. Queue capacity counts active nonterminal jobs/previews. Bulk jobs enqueue rows incrementally;
capacity checks serialized with DB advisory transaction lock to prevent concurrent overflow.
8. Graceful stop: stop claiming, finish current item within timeout, release lease/heartbeat.
Checks: crash before/after prediction commit, lease expiry, stale worker, retries exhausted,
duplicate item, preview starvation, capacity boundary, watchdog recovery.
Done: restart resumes exactly once in storage; at-least-once compute causes no count inflation.

### [ ] B03 — Preview service and routes
Owner: preview agent. Depends: B02.
Owns: backend/app/services/preview.py, backend/app/api/previews.py,
tests/integration/test_preview.py.
Steps:
1. POST analyze validates product/text/rating, verifies readiness/capacity, inserts preview; return 202.
2. Worker converts preview into Analysis DTO without inserting a review, mention run or product snapshot.
3. GET preview returns queued/running/completed/failed; no half-populated analysis object.
4. Implement TTL cleanup every 60 seconds; response expiry semantics in section 3.
5. Use exact text hash to match results; preview ID is unique and independent of submission.
Checks: preview leaves product counts unchanged; expiry; repeated calls; worker unavailable;
empty/no-aspect result; no raw review text in request logs.
Done: actual worker preview works end-to-end with the saved model bundle.

### [ ] B04 — Review submission, import and retry endpoints
Owner: ingestion agent. Depends: B02, C04.
Owns: backend/app/services/ingestion.py, import parsing, backend/app/api/reviews.py,
backend/app/api/jobs.py, tests/integration/test_ingestion.py.
Steps:
1. Implement section 5 write routes using idempotency keys (UUID, max 64 chars).
2. Inline review schema: review_text, rating?, source, external_review_id?, helpful_votes?, timestamp?.
Product is from path; reject body product mismatch. Manual source fields default server-side.
3. CSV UTF-8 with optional BOM; required review_text; optional rating/external_review_id/helpful_votes/timestamp.
JSON input is an array of the same row schema. Whole-file invalid syntax ->422, zero review inserts.
4. Stream file to controlled ignored temp directory; filename never determines filesystem path.
Enforce 10 MiB including chunked requests, <=5000 rows, per-text limits; reject binary/invalid encoding.
5. Once parseable, keep row-level validation failures with line/index numbers; valid rows can proceed.
Rejected rows count toward total_rows. Duplicate rows are recorded but not reinferred.
6. Import acceptance stores durable rows/items and safely removes temporary upload when no longer needed.
7. Retry endpoint creates new linked job for retryable failed items only; successes remain untouched.
Checks: wrong extension/MIME combinations, malformed quoting, numeric/rating validation,
duplicate imports, hostile filename, identical retry, failure midway, 0 valid rows, refresh-safe status.
Done: job accounting reconciles; client sees saved review IDs immediately; no duplicate submissions.

### [ ] B05 — Product insights, reviews and aggregate refresh
Owner: insights agent. Depends: B04, M07.
Owns: backend/app/services/insights.py, backend/app/api/products.py,
tests/integration/test_insights.py.
Steps:
1. List/search products and filtered reviews; stable order submitted_at DESC, id ASC for reviews.
Escape SQL LIKE wildcards in plain-text search; bind all parameters.
2. Build snapshots from saved compatible analysis runs, including analyzed no-aspect reviews.
3. Trigger aggregate job after analysis; coalesce product refresh requests, reject stale publish.
4. POST generate-tags rebuilds aggregates only; no model rerun and no prediction deletion.
5. Return last complete snapshot with stale=true until new version/revision finishes; never mix versions.
6. GET tags and GET insights share snapshot_id; review counts explicitly distinguish pending/failed/no-aspect.
7. Detail endpoint returns original text + matching prediction hash; filter evidence by selected aspect/sentiment.
Checks: zero/one/many reviews, old pipeline results excluded, late analysis, concurrent refresh,
missing product 404 vs empty existing product 200; regenerated results identical.
Done: UI-ready metrics and representative reviews match exact saved rows.

### [ ] B06 — Model metrics endpoint and observability
Owner: diagnostics agent. Depends: M04, B01.
Owns: backend/app/api/metrics.py, backend/app/telemetry.py,
tests/integration/test_metrics_api.py.
Steps:
1. Load approved machine-readable evidence, never hardcode scores in frontend.
2. Separate historical Kaggle and current inference evaluation with protocol, hashes, sample count,
label order, limitations and missing/Not run fields.
3. Correct derivative confusion-matrix metadata only; preserve original imported evidence.
4. Structured logs: request/job ID, pipeline version, stage, latency, counts, safe error codes.
No review bodies, usernames, credentials or absolute model paths in HTTP responses/logs.
5. Capture queued/running/failed counts, inference p50/p95, worker load count and model memory at benchmark.
Checks: absent/corrupt evidence -> typed unavailable response; matrix total matches test count;
no invented baseline; log scan with synthetic secret/review sentinels.
Done: figures trace to artifacts; diagnostics identify failure stages without exposing review contents.

### [x] D01 — Bounded Amazon sample with provenance
Owner: data agent. Depends: C01, C02.
Owns: scripts/sample_amazon.py, docs/datasets.md, audit/evidence/current/amazon-manifest.json,
tests/unit/test_amazon_sampling.py; writes real data only under ignored data/amazon/.
Steps:
1. Inspect official Amazon Reviews 2023 source and access/usage conditions; record exact URL,
immutable dataset revision if available, license/usage note and retrieval date.
2. Stream metadata to identify laptop products by category ancestry; do not classify laptop accessories
as laptops solely by review keywords. Bound metadata scan to 500,000 rows and reviews to 1,000,000 rows.
3. Select up to 50 eligible parent_asin IDs by seeded hash order; collect at most 100 reviews per product,
up to 5000 total. Prefer products with >=3 reviews for aggregation.
4. Retain source product ID, derived stable review ID, product name/category/brand, text, rating,
helpful_votes and timestamp. Drop user IDs/profiles, images and other unnecessary fields.
5. For missing review ID derive SHA-256(parent_asin + original timestamp + original text).
Record method and duplicate/malformed counts; review rating does not become a gold aspect label.
6. Manifest: source, revision, seed=42, selection rule, bounds, selected IDs, exact counts, hashes,
field inventory and limits. No full review text in committed manifest.
7. If scan bounds cannot reach 5000 laptop reviews, stop at bounds and report actual count;
never silently broaden to phones/accessories or fetch entire categories.
Checks: deterministic synthetic stream; duplicate exclusion, accessories rejected, missing product/text,
boundary stop, manifest count/hash verification.
Done: reproducible local sample with truthful coverage; no Amazon quality claim from unlabeled data.
Acquisition may require user acceptance if official source requires it; report exact requirement.

### [ ] D02 — Batch CLI and Amazon demonstration
Owner: batch agent. Depends: D01, B04, B05.
Owns: scripts/run_batch.py, tests/integration/test_batch_resume.py, docs/demo.md.
Steps:
1. Import selected products/reviews through the same services as API; chunk <=100 rows per transaction.
2. Derive idempotency keys from dataset hash + chunk index; reuse worker/job protocol.
3. Save resumable import cursor locally with dataset/pipeline hash; mismatched resume input fails.
4. Export product summaries and row errors locally; committed evidence contains counts/hash/aggregate timings only.
5. Choose three products with sufficient support; show raw evidence alongside model tags locally.
6. Clearly distinguish demo sample vs full Amazon population; no accuracy reported without gold labels.
Checks: interrupt halfway and resume; repeat full import leaves counts unchanged;
success+duplicate+rejected+failed reconciliation; cross-product isolation.
Done: real Amazon demo works through API/database, not a parallel one-off model script.

## 10. Frontend tasks and exact screens

### [x] F01 — React foundation and accessible application shell
Owner: frontend foundation agent. Depends: C01, C02.
Owns: frontend/package.json + lockfile, build/test config, src/routes/, src/styles/, shared primitives.
Steps:
1. Scaffold Vite React TypeScript; strict TS, lint, Vitest + Testing Library, Playwright.
2. Routes: / -> /products; /products; /products/:id; /products/:id/review;
 /products/:id/upload; /models.
3. Shared components: AppShell, PageHeader, Button, Field, Alert, Skeleton, EmptyState,
StatusBadge, SentimentBadge, DataTable, Dialog/Drawer.
4. Use restrained neutral layout with semantic positive/negative/neutral colors plus text/icons.
Desktop 2-column detail layout collapses to one column at mobile; tables scroll within their own container.
5. Top navigation: Products, Review analyzer (requires product selection), Imports, Model metrics.
6. Accessible labels, focus indication, landmarks, keyboard navigation and reduced-motion support.
Checks: typecheck/lint/unit/build; shell renders at 375/768/1440px without body overflow.
Done: no API logic in shell; all shared states reusable; lockfile committed.

### [ ] F02 — Generated client, query cache and mock contract server
Owner: frontend API agent. Depends: F01, B01.
Owns: frontend/src/api/, frontend/src/test/contract-fixtures/, client-generation script.
Steps:
1. Generate TypeScript types from contracts/openapi.json; no separately handwritten copies of DTOs.
2. API base URL uses VITE_API_BASE_URL; fetch wrapper handles error envelope and AbortSignal.
3. TanStack query keys include product_id/filter/page and snapshot metadata where applicable.
4. Implement read polling hooks and submit mutation; GET may retry boundedly, POST retry only with
same explicit Idempotency-Key. Keep that key while outcome is unknown.
5. Poll only while mounted and status nonterminal; pause when offline/hidden; resume on return.
6. Mock server uses C02 synthetic fixtures for tests/dev only; production requires real API.
Checks: abort, network loss, 422 fields, 429 retry-after, 503, stale responses, strict generated types.
Done: no hard-coded model labels/metrics in API client; generation diff checked in CI.

### [ ] F03 — Review editor and live preview session
Owner: review UI agent. Depends: F02, B03.
Owns: frontend/src/features/review/ReviewEditor, PreviewPanel, useReviewSession;
tests for these components.
Steps:
1. Product header + text area + optional 1–5 rating + Unicode code-point character counter.
2. "Preview tags" explicit button; no model inference per keystroke.
3. Store draft in sessionStorage under product-specific key; do not persist in localStorage by default.
4. Implement states idle, invalid, requesting, queued, analyzing, preview_ready, no_aspects, failed, expired.
5. Associate preview with exact text/rating fingerprint; editing cancels polling and clears stale highlights.
6. Keep user text after errors; distinguish preview tags from submitted/product-wide tags.
7. Render every unknown aspect with raw phrase and "Unrecognized aspect"; no fabricated tag.
Checks: empty/too long, emoji counting, edit during request, out-of-order results, retry, expired preview,
no aspects, model unavailable, keyboard-only path, draft restored per product.
Done: works with real preview endpoint; no product counts change before submission.

### [ ] F04 — Safe aspect highlights and evidence drawer
Owner: evidence UI agent. Depends: F02, M02.
Owns: frontend/src/components/ReviewHighlights, AspectEvidenceDrawer; unit tests.
Steps:
1. Offsets are Python Unicode code points, not JavaScript UTF-16 indices.
Use Array.from(review_text) for slicing or a tested code-point-to-UTF16 boundary map.
2. Sort/validate spans; render escaped text nodes and <mark>/<button>; never dangerouslySetInnerHTML.
3. Clicking a highlighted aspect opens canonical label, raw phrase, sentiment probabilities,
confidence labels and normalization status; indicate scores are uncalibrated.
4. Keyboard selection and drawer focus trap, Escape close, restore focus to trigger.
5. Long text wraps; repeated identical phrases highlighted by offsets; malformed API spans produce a
visible safe fallback list and diagnostic, not a broken page.
Checks: emoji before span, combining characters, repeated terms, hostile HTML, zero-length/out-of-range/
overlapping spans, tab order and focus restoration.
Done: displayed highlighted phrase equals API raw_aspect exactly for all fixtures.

### [ ] F05 — Submit, saved state and job recovery
Owner: session submission agent. Depends: F03, F04, B04.
Owns: SubmitReviewPanel, JobStatus, submission mutation and session tests.
Steps:
1. Generate idempotency UUID once per submission attempt; store key/job ID in sessionStorage.
2. POST only original text/rating; never trust browser-computed predictions.
3. On 202 clear saved draft, retain job pointer, show "Review saved; analysis queued".
4. Disable double-submit while response pending; lost response retries same key/body.
5. Poll job stages; display row failure even if review saved; retry uses job retry endpoint.
6. Completion invalidates product insights/reviews queries and links to product dashboard.
7. Page refresh reconstructs pending state; if content changes after saved review start a new draft.
Checks: double click, lost response, reload while queued, failure and retry,
success with preview absent, switching products, DB unavailable.
Done: one submitted review yields one stored review and one compatible analysis run.

### [ ] F06 — Product list and insights dashboard
Owner: dashboard agent. Depends: F02, B05.
Owns: frontend/src/features/products/ProductList, ProductDashboard, AspectTable, SentimentChart.
Steps:
1. Product list: search, pagination, name/category/review count, link to details.
2. Detail header: product identity, analyzed/pending/failed counts, snapshot time, stale indicator.
3. Strengths/weaknesses panels use API classifications and support; no recalculation of thresholds.
4. Aspect table: label, distinct review support, raw mentions, positive/neutral/negative counts+ratios,
aggregate tag; sortable by API numeric fields, name filter; separate insufficient-evidence section.
5. Sentiment chart displays review-aspect votes explicitly, with accessible data table and zero state.
6. Mixed/all-neutral aspects have their own section; one review never becomes an established strength.
7. Detail selection requests representative evidence via F04 drawer; paginate supporting reviews.
8. Stale snapshot remains visible as updating; never combine counts from two snapshot IDs.
Checks: arithmetic fixture, all neutral, 50/50, support 2 vs 3, empty product,
pending failures, unknown-only reviews, stale updates, chart/table equality, mobile overflow.
Done: every number reconciles to API, user can trace each tag to supporting reviews.

### [ ] F07 — Upload and import progress screen
Owner: import UI agent. Depends: F02, B04.
Owns: frontend/src/features/upload/, synthetic template download, tests.
Steps:
1. Product selector/header; CSV/JSON chooser; show schema and download a synthetic sample template.
2. Client validates extension/size; server remains authoritative. Do not evaluate CSV cell contents.
3. POST with idempotency key; store job ID; separate upload progress from model processing progress.
4. Show queued, validating, analyzing, aggregating, completed/error stages from backend.
5. Render actual counts; partial failure shows failed row indices and safe reasons.
6. Retry failed items only; no duplicate import on refresh or double click.
7. On completion link to product; pending polling resumes from sessionStorage.
Checks: oversized, binary, malformed, duplicate, offline/retry, partial failure, long job, navigation away/back.
Done: no fabricated progress percentages; accessible live status announcements are throttled.

### [ ] F08 — Metrics page and limitations
Owner: metrics UI agent. Depends: F02, B06.
Owns: frontend/src/features/metrics/, tests.
Steps:
1. Display A2 extraction and A3 sentiment historical/current results as separate labeled sections.
2. Show dataset count, checkpoint/pipeline version, protocol and evaluated date from endpoint.
3. Confusion matrix uses supplied row/column order with table alternative; never infer alphabetical order.
4. Missing normalization/end-to-end results read "Not run"; no zero masquerading as a measured score.
5. Explain neutral-class weakness, supported domain, unknown aspects and sample-level confidence limitations.
6. Include actual baseline comparison only where same evaluation protocol is verified.
Checks: misordered labels fixture, missing result, corrupted evidence error, all chart/table values.
Done: dashboard never attributes historical 0.750 to unevaluated clause-local behavior.

## 11. Operations, evaluation and release tasks

### [ ] O01 — Local startup and artifact provisioning
Owner: operations agent. Depends: B05, B06, F08.
Owns: compose.yaml, Dockerfiles, scripts/start_local.sh, docs/operations.md, .dockerignore.
Steps:
1. Compose services: postgres, migration one-shot, api, worker, frontend.
Worker alone mounts models read-only; API/worker share database; frontend calls configured API base URL.
2. Provision weights by documented local copy/private storage URI and known checksum.
Do not embed current developer machine paths or weights into image layers.
3. One command starts synthetic fixture mode; a separate explicit command starts real-model mode.
Fixture mode displays a visible banner and does not become a claimed real-model release.
4. Bind ports to loopback in local configuration; keep persistent DB volume; health checks use /ready.
5. Apply migrations once before services; waiting for worker availability must not restart healthy API endlessly.
6. Document startup, shutdown, restart, logs, backup/restore, artifact verification and disk/memory needs.
7. Define data retention: preview TTL 30 minutes; uploaded temp files removed after ingest;
saved demo reviews persist until explicit administrative cleanup. Never use broad rm commands.
Checks: compose config; clean build; missing models -> not ready; real weights mount/reload;
restart preserves reviews/results; restored backup reproduces snapshot.
Done: clean-clone instructions distinguish downloadable artifacts from source code.

### [ ] O02 — CI and test separation
Owner: CI agent. Depends: O01, Q01.
Owns: .github/workflows/ci.yml, marker config and CI docs.
Steps:
1. PR CI: core unit, Postgres integration with model fakes, schema generation/diff,
frontend typecheck/lint/unit/build, synthetic browser E2E.
2. Real-model suite runs locally or explicit authorized private runner with verified artifacts;
never download private weights in untrusted PR jobs.
3. Keep credentials/secrets out of build logs; scan tracked artifact paths/sizes and actual staged secrets.
4. Split tests currently using ReviewAnalyzer() into explicit heuristic/fake tests and marked transformer tests.
5. Cache dependencies by lockfile; no training, full Amazon ingestion, or hidden model downloads in normal CI.
Checks: deliberately broken contract fails CI; fake suite runs without models;
real suite missing artifacts fails its release job rather than reporting PASS.
Done: test output clearly states executed, skipped and blocked; no false release assurance.

### [ ] O03 — Accurate documentation and reproducibility record
Owner: documentation agent. Depends: Q02, O02.
Owns: README.md, docs/architecture.md, docs/winning-model.md, docs/demo.md,
audit/evidence/winning-run.json, docs/contracts/ and docs/operations.md corrections.
Steps:
1. Replace stale "pending transfer/dependencies" and "fallback-only" statements using verified results.
2. Separate checkpoint preservation, load verification, historical metrics and current pipeline validation.
3. Document commands for setup, API/worker/UI, synthetic demo, real Amazon demo and tests.
4. Explain no customer-session retraining, model version changes, normalization unknowns and threshold support.
5. Record manifest field algorithm meanings and corrected A3 matrix provenance.
6. Include reproducible release commands/version hashes and known unresolved limitations.
Checks: replay documented setup from isolated checkout; links/paths exist;
metrics match approved artifacts; no ignored TODO files force-added.
Done: someone without this chat can run the demo and understand its quality limits.

### [ ] Q01 — Independent integration and browser verification
Owner: read-only verification agent. Depends: F05, F06, F07, F08, B05, B06.
Owns: tests/integration/test_full_session.py, frontend E2E tests, audit/evidence/current/session-report.md.
The verifier writes tests/reports but does not silently fix implementation bugs; file findings to owners.
Steps:
1. Create synthetic product -> preview -> confirm no aggregate changes -> submit -> poll ->
inspect stored analysis -> inspect snapshot -> browse evidence.
2. Repeat submission with same key, replay import, restart worker mid-job, refresh UI and retry failures.
3. Exercise real API with synthetic fakes in CI; additionally run real model flow locally.
4. Inspect keyboard navigation, accessibility scan, 375/768/1440px, focus management,
console/network errors, no unsafe HTML rendering.
5. Trace review hash/pipeline version from request through DB to highlighted UI result.
6. Verify input privacy logs, limits, CORS, and recovery from unavailable DB/model.
Checks: every acceptance scenario in section 13; capture actual commands, exit codes and screenshots.
Done: no unresolved critical/high issues; actual backend and browser used, not screenshots alone.

### [ ] Q02 — Independent model and real-data acceptance
Owner: ML audit agent. Depends: M08, D02, Q01.
Owns: audit/evidence/current/model-release-report.md, tests/model/ release checks.
Steps:
1. Check checkpoint + split hashes and original/derived evidence separation.
2. Rerun current model quality gates, normalization gate, and combined Tag F1 evaluation.
3. End-to-end gold: prepare 200 independently annotated held-out reviews, chosen before evaluation
from an eligible evaluation source; labels include exact span, canonical ID and sentiment.
Use validation-only data for implementation tuning; obtain human review for gold labels.
4. Tag true positive requires same review, exact start/end, canonical ID, and sentiment.
One-to-one match; calculate precision/recall/micro-F1 with explicit empty-set semantics.
5. Require end-to-end Tag F1 >=0.60; report all component gates and errors, not only successes.
6. Benchmark warm 100-review sample and 5000-review batch on recorded hardware.
Initial local target: p95 <5s for <=256-token single reviews at concurrency 1; report peak RSS.
If target missed, profile and raise optimization tasks; do not omit slow cases or change targets silently.
7. Compare full-review historical protocol to selected current policy; requested example must pass,
but cannot override a failing held-out gate.
Checks: reviewed gold existence, no tuning on held-out set, deterministic repeat, output hashes.
Done: quality claims reproducible; human annotation missing -> explicitly BLOCKED quality gate,
even if model loading and demo work.

### [ ] Q03 — Final release rehearsal and handoff
Owner: integration lead. Depends: O03, Q02.
Owns: audit/reports/release.md and final user handoff.
Steps:
1. Freeze release SHA; rerun required checks once on that exact candidate.
2. Recreate app in isolated checkout with separate disposable DB and provisioned weights.
3. Run synthetic session and bounded Amazon session from docs.
4. Reconcile API, DB and UI totals and verify no real-data/checkpoint/secret assets tracked.
5. Report measured model quality, latency, remaining limits and evidence links.
6. Publish/deploy only if separately authorized; this checklist does not choose a paid provider.
Checks: clean startup; browser session; retry/resume; migrations; restart persistence;
dependency/security checks relevant to enabled local/public mode.
Done: local MVP accepted; deployment/public auth remains a separately approved phase.

## 12. Dispatch order and parallel work map

Use task dependencies as authoritative; waves are suggested resource scheduling, not permission to skip dependencies.

| Wave | Startable assignments | Exit condition |
|---|---|---|
| 0 | C01 | Project installs, settings and test markers stable |
| 1 | C02 and M01 | DTO fixtures and strict loader ready |
| 2 | C03, M02, M05, D01, F01 | Schema, extraction, ontology, sample and shell ready |
| 3 | C04, B01, M03, M06 | Repositories, API shell and sentiment/templates ready |
| 4 | M04, M07, F02 | Frozen context evaluation, aggregation and typed client ready |
| 5 | M08; F04 can run in parallel | Integrated model bundle and highlight component ready |
| 6 | B02 | Durable worker ready |
| 7 | B03, B04, B06 | Preview, ingestion/job and metrics routes ready |
| 8 | B05, F03, F07, F08 | Insights and primary pages ready |
| 9 | D02, F05, F06 | Real-data batch and complete user flows ready |
| 10 | Q01, then O01 and Q02 in parallel | Integration evidence, startup, quality evidence |
| 11 | O02 -> O03 -> Q03 | CI, docs and final rehearsal complete |

File collision rules:
- M01/M02/M03 each touch transformer_models.py sequentially in the order above.
- C02 completes schema adapters before M08 composes them.
- M05 defines ontology; M06 changes template fields after M05 completes.
- F01 owns frontend dependency/config files; other frontend agents request updates through F01 owner.
- C03 owns migrations; service agents do not independently create migrations.
- O03 owns final docs reconciliation after implementation.
- Changes to section 5 require integration lead approval and regenerate OpenAPI/client together.
- No worker agent changes shared model behavior just to make its own endpoint pass.

Small-agent prompt template:
"""
Implement task <ID> from local TODO.md only.
Read sections 1–7, your task, the frozen contracts and dependency handoffs.
Your writable scope is the task's Owns paths; other files are read-only unless the lead assigns them.
Dependencies passed: <IDs + evidence>.
Use the specified versions, state machine and errors. Do not invent an API.
Run the listed task checks; report exact results. Do not mark skipped checks as passed.
Stop only for an actual missing input/authority/contract conflict; continue independent checks.
Return the required handoff and any findings. Do not deploy or push unrelated changes.
"""

Integration lead checklist per handoff:
- [ ] Dependency evidence exists and corresponds to current code.
- [ ] Changes match owned files and frozen interfaces.
- [ ] Tests exercise outcomes, failures and boundaries, not only implementation details.
- [ ] Unit tests do not silently load real models or network.
- [ ] Domain results are not fabricated or silently substituted with fallback.
- [ ] Worker/API/database/UI agree on pipeline and snapshot versions.
- [ ] No TODO, raw datasets, private weights, archives or credentials are staged.
- [ ] Mark task complete only after acceptance; update blocked dependents if needed.

## 13. Mandatory release scenarios

| ID | Scenario | Expected result | Owner |
|---|---|---|---|
| S01 | Amazing display but terrible battery. | Display positive / Battery negative, valid spans; actual transformer backend | M08 |
| S02 | Review contains only unrelated text | Empty mentions; successful analysis; no product tags invented | M08 |
| S03 | Unknown extracted noun | Unknown normalization, null canonical tag, visible raw aspect | M05/F03 |
| S04 | Battery + battery life repeated in one review | Raw mentions retained, one Battery review vote | M07 |
| S05 | Opposing sentiments for same feature in one review | Contradiction tracked; one neutral aggregate vote | M07 |
| S06 | Two supporting reviews | Insufficient evidence; no top product strength | M07/F06 |
| S07 | Third supporting review arrives | Snapshot refresh; support and classification recomputed atomically | B05 |
| S08 | Preview then abandon page | Product review/aggregate totals unchanged | B03 |
| S09 | Submit same key twice concurrently | One job and one logical saved review | C04/B04 |
| S10 | Same key reused for changed text | HTTP 409 | C04 |
| S11 | Worker crashes after commit before acknowledgment | Retry creates no duplicate analysis or counts | B02 |
| S12 | Model missing/corrupt | Worker not ready; HTTP 503 on new analysis; no rule result | M01/B01 |
| S13 | Feature after token 256 | Extracted through later window with source offsets | M02 |
| S14 | Emoji before highlighted aspect | Browser highlight exactly matches source phrase | F04 |
| S15 | Identical sentence repeated twice | Context selected by actual occurrence | M03 |
| S16 | Text edit while preview queued | Old results discarded; submit uses new text | F03 |
| S17 | Upload malformed/oversized/binary file | Defined 4xx; no partial unintended ingestion | B04 |
| S18 | CSV contains some invalid rows | Valid rows processed; rejected and failed totals distinct | B04 |
| S19 | Same Amazon sample imported twice | No duplicated review counts | D02 |
| S20 | Model/pipeline version changes | Old predictions not mixed into current snapshot | B05 |
| S21 | Script markup in review | Displayed literally, never executes | F04/Q01 |
| S22 | Only neutral votes | Neutral class and tag; not mislabeled as positive/negative/mixed opinion | M07 |
| S23 | Current evaluation missing | UI says Not run; historical score clearly identified | F08 |
| S24 | Restart DB/API/worker after review saved | Saved data retained, unfinished jobs recover | O01 |
| S25 | GET insights and tags around regeneration | Snapshot IDs allow client to avoid combining revisions | B05/F06 |

## 14. Evidence gates and what the user must eventually supply

G0 foundation: C01–C04 pass, valid contracts/migrations, tracked-file audit.
G1 model: M01–M08 pass with current-policy evidence; historical A2/A3 are not substitutes.
G2 application: B01–B06 and D01–D02 pass, job retries and data provenance verified.
G3 interface: F01–F08 and Q01 pass, real API session and safe highlights verified.
G4 release: O01–O03 and Q02–Q03 pass on exact release candidate.

Nothing new is needed from the user to begin C01/C02 and strict loader work.
Potential concrete future inputs:
- Human review of normalization and end-to-end gold annotations before formal accuracy claims.
- Dataset access acceptance only if the official source requires it.
- Private artifact location accessible to another machine for reproducible real-model setup.
- Hosting/public access/auth decisions only when deploying beyond the loopback demo.

Do not request these choices prematurely. Implement and test the authorized local workflow first.
Keep the existing weights and their historical evidence intact. If current quality gates fail,
report the failure and propose a separate targeted training/data task; do not call the MVP complete.
