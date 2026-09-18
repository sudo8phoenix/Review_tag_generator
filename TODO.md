# Automated E-Commerce Review Tag Generator - Agent TODO

This document turns the approved build plan into small, dependency-aware assignments. It is the execution contract for work agents, audit agents, and the root/integration agent.

Source plan: `Automated_Ecommerce_Review_Tag_Generator_Build_Plan.md`

## 1. Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Work complete and audit passed
- `[!]` Blocked by an audit finding or missing dependency

An implementation task is not complete until its named audit gate passes. Training, evaluation, and release claims must be supported by reproducible evidence rather than notebook output or screenshots alone.

## 2. Non-Negotiable MVP Scope

Build for laptops and consumer electronics first. The MVP pipeline is:

```text
review text
  -> conservative preprocessing
  -> DistilBERT aspect extraction (BIO token classification)
  -> DistilBERT aspect-level sentiment classification
  -> MiniLM/cosine aspect normalization
  -> deterministic tag generation
  -> product aggregation and ranking
  -> PostgreSQL + FastAPI
  -> React/TypeScript dashboard
```

Do not add external LLM calls, live Amazon scraping, microservices, Kafka, Kubernetes, a mobile app, multiple databases, generative tag wording, optional comparison/trends pages, or additional product domains before the MVP and release audit pass.

## 3. Agent Operating Contract

### Work Agent

For each assignment, the work agent must:

1. Accept exactly one task ID and verify every dependency is complete.
2. Read the source plan and all contracts used by the task.
3. Change only the assigned subsystem, its tests, and directly related documentation.
4. Keep shared schemas, label maps, thresholds, and API shapes unchanged unless the task explicitly owns them.
5. Add deterministic fixtures and automated tests for every new behavior and failure mode.
6. Never commit raw/restricted datasets, model checkpoints, database volumes, credentials, `.env` files, caches, or build output.
7. Run the task's checks and provide the handoff format below.
8. Stop and report a contract conflict instead of silently inventing a new interface.

### Audit Agent

The audit agent is an independent, read-only verifier. It must not edit implementation files, implement fixes, train replacement models, weaken tests, change frozen thresholds after seeing test results, selectively regenerate evidence, or approve its own work.

For each gate, the audit agent must:

1. Audit an exact commit SHA after all gate dependencies are complete.
2. Inspect both the work-agent diff and the dependency artifacts it consumes.
3. Run the named checks independently, including adversarial and boundary cases.
4. Record exact commands, exit codes, environment, inputs, dataset/model revisions, and raw results.
5. Return `PASS` only when every required check ran, every acceptance criterion passed, and no Critical or High finding remains open.
6. Return `BLOCKED` when a required check is skipped, evidence is missing, a metric floor is missed, a test/build fails, or a Critical/High finding remains.
7. File findings with severity, path/symbol or endpoint, exact reproduction, expected result, actual result, risk, owner, required remediation, and downstream gates to rerun.
8. Re-run the failed check and relevant regression suite after remediation without deleting the original failure evidence.

### Required Handoff From Every Work Agent

```markdown
Task: TXX
Commit: <sha>
Files changed: <paths>
Commands run: <exact commands>
Results: <exit codes and key metrics>
Fixtures/data/model versions: <identifiers and hashes>
Known limitations: <explicit list or none>
Contract changes: <none unless task owns them>
Ready for audit gate: <AX>
Next tasks unblocked: <IDs>
```

### Required Audit Artifacts

Future implementation work must maintain:

```text
audit/audit-register.md
audit/findings.md
audit/reports/gate-A0.md ... gate-A8.md
audit/evidence/A0/ ... A8/
```

Evidence is invalid when it lacks the audited commit SHA, exact command, input/model/dataset version, or raw output. Screenshots may support UI findings but cannot replace executable checks.

## 4. Frozen Shared Contracts

Task T01 owns the definitive schemas. Until T01 is complete, later agents must use these minimum shapes and may only extend them compatibly.

```text
Review: review_id, product_id, product_category, review_text, rating,
        helpful_votes, timestamp, annotations[]
AspectAnnotation: aspect, normalized_aspect, opinion, sentiment,
                  start_char, end_char
AspectPrediction: aspect, start_char, end_char, confidence
SentimentPrediction: label, confidence, probabilities{positive,neutral,negative}
NormalizationResult: raw_aspect, normalized_aspect|null, similarity, is_unknown
TagResult: normalized_aspect|null, sentiment, tag, confidence
ProductTag: product_id, normalized_aspect, tag, counts, ratios,
            mention_count, average_confidence, score, rank
```

Required callable interfaces:

```python
extract_aspects(text) -> list[AspectPrediction]
predict_sentiment(review, aspect) -> SentimentPrediction
normalize_aspect(aspect) -> NormalizationResult
generate_tag(normalized_aspect, sentiment) -> str
analyze_review(review) -> list[TagResult]
```

Required API surface:

```text
POST /api/reviews/analyze
POST /api/products/{product_id}/reviews
POST /api/products/{product_id}/generate-tags
GET  /api/products/{product_id}/tags
GET  /api/products/{product_id}/insights
GET  /api/products
GET  /api/jobs/{job_id}
GET  /health
GET  /ready
```

## 5. Work Tasks

### [ ] T00 - Repository and Project Foundation

- **Depends on:** Planning documents published.
- **Owns:** Root configuration, directory skeleton, README, ignore rules, environment examples.
- **Instructions:** Create the source-plan directory structure for `data`, `ml`, `models`, `backend`, `frontend`, `notebooks`, `tests`, `audit`, and `docs`. Add Python 3.11 and Node version declarations, `.editorconfig`, comprehensive `.gitignore`, root README, and example environment files containing names only, never credentials. Document where datasets and model checkpoints must be placed without committing them.
- **Tests:** Run `git diff --check`; inspect `git ls-files`; scan tracked paths for `.env`, raw data, checkpoints, virtual environments, `node_modules`, and build output.
- **Acceptance:** A clean clone has clear setup prerequisites and the expected structure; prohibited artifacts and secrets are untracked; the original plan remains unchanged.
- **Evidence:** Tracked-file list, secret/artifact scan, setup/version output.
- **Audit:** A0.

### [ ] T01 - Shared Schemas and Configuration

- **Depends on:** T00.
- **Owns:** Cross-module types, label maps, config, contract documentation.
- **Instructions:** Implement the frozen review, annotation, span, sentiment, normalization, tag, aggregate, insight, and processing-job schemas. Define `O/B-ASP/I-ASP` IDs and positive/neutral/negative IDs once. Centralize random seeds, model revisions, paths, max lengths, aggregation thresholds, and ranking options. Include character offsets for UI highlighting and version the contracts.
- **Tests:** Schema round trips, invalid enum/offset/rating rejection, canonical source-plan example validation, config override tests.
- **Acceptance:** Every example validates; invalid offsets and labels fail clearly; later modules can import contracts without redefining wire shapes.
- **Evidence:** Test output and rendered contract examples.
- **Audit:** A0.

### [ ] T02 - Dataset Acquisition and Provenance

- **Depends on:** T00.
- **Owns:** Download/preparation scripts and dataset manifest.
- **Instructions:** Add reproducible acquisition instructions/scripts for Laptop-ACOS, SemEval 2014 Laptop ABSA, and a bounded Amazon Reviews 2023 sample. Record official source URL, version/revision, checksum, license/usage note, retrieval date, expected raw path, and whether manual acceptance is required. Do not redistribute restricted/raw data.
- **Tests:** Run acquisition in validation/dry-run mode; verify checksum failures and missing manual downloads produce actionable errors.
- **Acceptance:** A clean environment can populate the expected paths or receives exact manual steps; no raw dataset is tracked.
- **Evidence:** Manifest, command logs, source/license citations, checksums.
- **Audit:** A1.

### [ ] T03 - Laptop-ACOS Converter

- **Depends on:** T01, T02.
- **Owns:** Laptop-ACOS parser, fixture, conversion report.
- **Instructions:** Parse the official format structurally. Preserve review text, aspect/opinion text, categories, sentiment, and offsets when available. Generate stable source-aware IDs, validate every output record, and log rejected records with reasons. Emit the common JSONL format deterministically.
- **Tests:** Golden examples for explicit and implicit aspects, multiple annotations, missing fields, malformed records, offset validation, and repeated-run byte stability.
- **Acceptance:** Fixture annotations round-trip exactly; every emitted record validates; counts plus rejections reconcile with input.
- **Evidence:** Conversion summary, rejected-row summary, fixture test output.
- **Audit:** A1.

### [ ] T04 - SemEval Laptop Converter

- **Depends on:** T01, T02.
- **Owns:** SemEval XML parser, fixtures, conversion report.
- **Instructions:** Parse XML with an XML parser. Preserve official train/test boundaries, sentence text, aspect terms, polarity, and character spans. Handle absent/conflict polarity explicitly rather than guessing. Validate every extracted substring against its annotated span.
- **Tests:** XML fixture tests for multiple aspects, special characters, absent/conflict entries, bad offsets, and official split retention.
- **Acceptance:** Extracted substrings equal annotated terms; official counts reconcile or every discrepancy is documented; output validates.
- **Evidence:** Split counts, discrepancy report, test output.
- **Audit:** A1.

### [ ] T05 - Preprocessing, Deduplication, Splits, and Statistics

- **Depends on:** T03, T04.
- **Owns:** Cleaning library, model-ready splits, statistics generator.
- **Instructions:** Remove HTML, normalize whitespace and malformed characters, optionally remove URLs/emails, segment sentences, and handle empty/short reviews while preserving punctuation, negation, terminology, and span mappings. Remove exact duplicates. Retain official splits where available; otherwise use deterministic stratified splitting grouped to prevent review/product leakage. Produce label, aspect, length, rejection, and source statistics.
- **Tests:** Cases for `isn't good`, HTML, Unicode/emoji, URL/email, blank/short review, multi-sentence text, duplicate sources, and offsets before/after cleaning.
- **Acceptance:** No duplicate crosses splits; transformations are deterministic; negation and valid spans survive; counts reconcile.
- **Evidence:** Split manifests/hashes, before/after counts, distribution tables, tests.
- **Audit:** A1.

### [ ] T06 - Classical Baselines

- **Depends on:** T05.
- **Owns:** Whole-review sentiment, logistic sentiment, and rule/spaCy aspect baselines.
- **Instructions:** Implement a whole-review sentiment baseline for the product demo, a TF-IDF/logistic-regression aspect-sentiment baseline, and a rule/spaCy noun/aspect extractor. Fit preprocessing and vocabulary on training data only. Save configurations and machine-readable held-out metrics.
- **Tests:** Deterministic fixture predictions, serialization reload, held-out evaluation smoke test.
- **Acceptance:** Extraction precision/recall/F1 and sentiment accuracy/Macro-F1 are reproducible and available for transformer comparison.
- **Evidence:** Metrics JSON/CSV, seeds, fitted-artifact hashes, comparison template.
- **Audit:** A2 for extraction and A3 for sentiment.

### [ ] T07 - BIO Labels and Token Alignment

- **Depends on:** T01, T05.
- **Owns:** Aspect-extraction dataset builder.
- **Instructions:** Convert character spans to BIO tags; tokenize with a pinned DistilBERT tokenizer revision and offsets; assign `-100` to special/padding tokens; document the first-subtoken/continuation policy; detect overlap and truncation rather than silently corrupting labels; provide human-readable alignment debugging.
- **Tests:** Single-token, multi-token, WordPiece-split, repeated, punctuation-adjacent, overlapping, truncated, and malformed spans.
- **Acceptance:** Golden token/label/offset arrays match exactly and malformed spans fail with actionable errors.
- **Evidence:** Alignment fixture output, tokenizer revision, tests.
- **Audit:** A2.

### [ ] T08 - Aspect Extractor Training

- **Depends on:** T07.
- **Owns:** DistilBERT token-classification training and checkpoint manifest.
- **Instructions:** Implement seeded training with configurable batch size, max length, learning rate, 3-5 epochs, AdamW, early stopping, and validation `seqeval` F1 checkpoint selection. Support a tiny CPU smoke configuration. Save the best checkpoint outside Git, plus config, dataset hash, seed, environment, and checkpoint hash.
- **Tests:** CPU smoke training, resume/config validation, checkpoint load test.
- **Acceptance:** No test split influences selection; best checkpoint reloads; every run is attributable to exact data/config/model revisions.
- **Evidence:** Training logs, manifest, validation history, checkpoint hash.
- **Audit:** A2.

### [ ] T09 - Aspect Extractor Evaluation and Inference

- **Depends on:** T08.
- **Owns:** `extract_aspects`, held-out evaluation, error report.
- **Instructions:** Reconstruct exact character spans from BIO predictions, merge subwords, deduplicate identical spans, and return text, offsets, and confidence. Compute exact-span precision/recall/F1 separately from token accuracy. Export false-positive/false-negative samples without tuning on the test set.
- **Tests:** Empty, no-aspect, multi-aspect, repeated-aspect, multiword, punctuation, negation, and long/truncated review inputs.
- **Acceptance:** Returned offsets reproduce source substrings; inference is stable; exact-span F1 is at least `0.70` and beats the rule baseline.
- **Evidence:** Metrics, checkpoint/data hashes, inference fixtures, error categories.
- **Audit:** A2.

### [ ] T10 - Aspect-Sentiment Pair Builder

- **Depends on:** T01, T05.
- **Owns:** Review/aspect classification datasets.
- **Instructions:** Produce `(review_text, aspect_text)` tokenizer pairs and stable positive/neutral/negative labels. Preserve source IDs and aspect offsets, keep aspects visible when truncating, deduplicate pairs, prevent leakage, and report class balance.
- **Tests:** Multiple aspects in one review, repeated aspects, neutral/conflict labels, long reviews, truncation, and duplicate sources.
- **Acceptance:** Every retained annotation maps to exactly one correct pair/label; splits remain isolated; counts reconcile.
- **Evidence:** Pair counts, label distribution, split hashes, tests.
- **Audit:** A3.

### [ ] T11 - Aspect Sentiment Training

- **Depends on:** T10.
- **Owns:** DistilBERT sequence-classification training and checkpoint manifest.
- **Instructions:** Implement seeded three-class training with early stopping on validation Macro-F1, configurable class weighting, CPU smoke mode, and best-checkpoint persistence. Log accuracy, per-class precision/recall/F1, and Macro-F1 without consulting the test set.
- **Tests:** Smoke training, label-map consistency, config validation, checkpoint reload.
- **Acceptance:** Best checkpoint selection uses validation only and can be reproduced from the manifest.
- **Evidence:** Training logs/history, manifest, label map, hashes.
- **Audit:** A3.

### [ ] T12 - Sentiment Evaluation and Inference

- **Depends on:** T11.
- **Owns:** `predict_sentiment`, held-out evaluation, confusion matrix.
- **Instructions:** Return the predicted label, confidence, and probabilities for all three classes. Produce accuracy, macro precision/recall/F1, per-class recall, confusion matrix, and categorized errors. Confirm predictions are conditioned on the requested aspect rather than the review alone.
- **Tests:** `good camera but poor battery`, neutral aspect, negation, contradiction, repeated aspect, invalid/empty aspect, probability sum and label-map checks.
- **Acceptance:** Probabilities sum to one; labels are not inverted; Macro-F1 is at least `0.65`, every class recall is at least `0.50`, and Macro-F1 beats the classical baseline.
- **Evidence:** Metrics/confusion matrix, hashes, adversarial predictions, errors.
- **Audit:** A3.

### [ ] T13 - Canonical Laptop/Electronics Aspect Ontology

- **Depends on:** T05.
- **Owns:** Versioned ontology schema/data and validation.
- **Instructions:** Define canonical IDs, display labels, synonyms, and positive/negative/neutral templates for the Phase-1 aspect set in the source plan. Resolve or document ambiguity among display/screen, price/value, camera, charging, delivery, and service terms. Prevent one synonym from silently belonging to conflicting aspects.
- **Tests:** Schema validation, unique canonical IDs, synonym-collision detection, complete label/template coverage.
- **Acceptance:** Every scoped aspect has a stable ID/display label and every conflict has an explicit rule or is rejected.
- **Evidence:** Ontology version/hash, validation output, frequency coverage.
- **Audit:** A4.

### [ ] T14 - Semantic Aspect Normalizer

- **Depends on:** T13.
- **Owns:** `normalize_aspect`, MiniLM revision, mapping evaluation.
- **Instructions:** Pin `sentence-transformers/all-MiniLM-L6-v2`; cache canonical/synonym embeddings; compute cosine similarity; return the best canonical ID and score or explicit unknown below the frozen threshold. Label 100-300 mappings, use separate threshold-tuning and held-out sets, and never tune on held-out results.
- **Tests:** Exact synonyms, paraphrases, case/plural variants, ambiguous `charge`, unrelated nouns, ontology collisions, and values just below/above threshold.
- **Acceptance:** Unknown inputs are not force-mapped; held-out normalization accuracy is at least `0.80`; revision, threshold, and evaluation data hashes are reproducible.
- **Evidence:** Mapping data card, tuning curve, frozen threshold, held-out metrics.
- **Audit:** A4.

### [ ] T15 - Deterministic Mention-Level Tag Generator

- **Depends on:** T13.
- **Owns:** `generate_tag` and template coverage.
- **Instructions:** Convert canonical aspect plus positive/negative/neutral sentiment to readable deterministic wording. Use ontology templates and a stable display-label fallback. Reject invalid IDs; never expose snake_case or call a generative model/API.
- **Tests:** Every canonical aspect across all sentiments, invalid/unknown aspect, deterministic repeat, source-plan examples.
- **Acceptance:** `camera_quality + positive` yields `Excellent Camera`; `battery_life + negative` yields `Poor Battery Life`; all ontology entries are covered.
- **Evidence:** Coverage table and unit-test output.
- **Audit:** A4.

### [ ] T16 - Product Aggregation and Ranking

- **Depends on:** T01, T15.
- **Owns:** Product-level aggregation, tag classification, ranking.
- **Instructions:** Group mentions by product/canonical aspect; calculate positive/neutral/negative counts and ratios, average confidence, and mention totals. Default minimum mentions to `3`. Apply positive thresholds 80%/60%, negative thresholds 70%/50%, else mixed. Rank with `log(1 + mention_count) * average_confidence * abs(positive_ratio - negative_ratio)`. Keep helpfulness disabled by default unless normalized/documented. Add deterministic tie-breaking and idempotent regeneration.
- **Tests:** Hand-calculated fixtures, zero/all-neutral/balanced cases, duplicates, missing confidence, Top-K bounds, tie order, rerun idempotency.
- **Acceptance:** Counts and ratios reconcile; no NaN/divide-by-zero; expected tags/order match golden fixtures; representative reviews match displayed aspect/sentiment.
- **Evidence:** Golden calculations, property tests, output fixtures.
- **Audit:** A4.

### [ ] T17 - Central End-to-End Inference Pipeline

- **Depends on:** T09, T12, T14, T15.
- **Owns:** Reusable `analyze_review` pipeline.
- **Instructions:** Compose preprocessing -> extraction -> aspect sentiment -> normalization -> tag generation. Load models once per process, preserve source offsets, return both model confidences plus normalization score, use configured model paths/device, and define empty/no-aspect/unknown/model-load behavior.
- **Tests:** Source-plan example, multiple aspects, negation, no aspect, duplicates, contradictory sentiment, Unicode, malformed/empty input, long input, model-load failure, repeated-call load count.
- **Acceptance:** `Amazing display but terrible battery.` returns the two expected aspect-level tags with valid offsets; no-aspect returns an empty list; held-out end-to-end Tag F1 is at least `0.60`; repeated calls do not reload models.
- **Evidence:** Golden suite, latency/memory measurement, model/data hashes, metrics.
- **Audit:** A5.

### [ ] T18 - Amazon Demo Sample and Offline Batch Processor

- **Depends on:** T02, T17.
- **Owns:** Bounded sampling, batch inference, resumability.
- **Instructions:** Select 5,000-50,000 laptop/electronics reviews for inference/demo only. Retain only required product/review fields; exclude reviewer PII. Process in batches with checkpoints, deterministic product selection, failure logs, resumability, and final counts. Commit only tiny synthetic/redacted fixtures.
- **Tests:** Interrupted/resumed batch, duplicate rows, malformed rows, empty text, missing product ID, partial failures, rerun idempotency.
- **Acceptance:** Success/skipped/failed counts reconcile; resume creates no duplicate outputs; provenance is traceable; raw/full data stays untracked.
- **Evidence:** Sampling manifest, processor log, summary, privacy field inventory.
- **Audit:** A5.

### [ ] T19 - PostgreSQL Schema and Alembic Migrations

- **Depends on:** T01.
- **Owns:** Database configuration, ORM models, migrations.
- **Instructions:** Implement products, reviews, aspect mentions, product tags, and processing jobs with primary/foreign keys, unique external IDs, indexes, numeric constraints, timestamps, and documented cascade behavior. Configure SQLAlchemy sessions and Alembic. Keep credentials in runtime environment only.
- **Tests:** Upgrade from empty DB, downgrade/upgrade in disposable DB, constraints, relationships, duplicate IDs, cascades, numeric precision, transaction rollback.
- **Acceptance:** Migrations succeed cleanly; duplicate behavior is deterministic; no orphan records or credentials are committed.
- **Evidence:** Migration logs, schema inspection, DB tests.
- **Audit:** A6.

### [ ] T20 - Backend Service Layer

- **Depends on:** T16, T17, T18, T19.
- **Owns:** Persistence repositories, ingestion/inference/aggregation services.
- **Instructions:** Implement product/review repositories, single-review analysis, CSV/JSON validation, batch job state transitions, tag regeneration transaction, insights queries, representative-review selection, and a typed error taxonomy. Make duplicate ingestion idempotent and prevent partial tag replacement on failure.
- **Tests:** Service tests with model fakes and disposable DB for success, malformed rows, duplicates, partial failure, rollback, empty products, and representative-review correctness.
- **Acceptance:** Services run without HTTP; failures leave consistent state; duplicate ingestion/regeneration does not inflate counts.
- **Evidence:** Service-test output, transaction fixtures, state-transition table.
- **Audit:** A6.

### [ ] T21 - FastAPI Application and Endpoints

- **Depends on:** T20.
- **Owns:** HTTP routes, Pydantic I/O, error mapping, OpenAPI.
- **Instructions:** Implement the frozen API surface. Add request/response validation, file type/size and review length limits, pagination, health/readiness distinction, environment-specific restricted CORS, safe exception mapping, batch partial-failure semantics, and OpenAPI examples. Treat public admin/upload endpoints as protected; for a local-only academic demo, bind and document that limitation explicitly.
- **Tests:** Contract tests for success/4xx/5xx, malformed JSON/CSV, binary or oversized upload, duplicate IDs, unknown product, repeated generation, concurrency, stored HTML/script text, health/readiness, and OpenAPI schema.
- **Acceptance:** Contracts match documentation; malformed/hostile input cannot corrupt state or expose traces/secrets; uploads and inference are bounded.
- **Evidence:** API test logs, OpenAPI snapshot, security-case results.
- **Audit:** A6.

### [ ] T22 - React Foundation and Typed API Client

- **Depends on:** T17 contract stable; T21 preferred.
- **Owns:** Vite/React/TypeScript/Tailwind/Recharts setup, shell, routes, API client.
- **Instructions:** Do not start until the end-to-end ML pipeline works. Create the application shell, navigation, routes, restrained dashboard design tokens, accessible primitives, environment-configured API client, and standard loading/empty/error/offline states. Generate or type the client from the OpenAPI contract. Do not hard-code production demo responses.
- **Tests:** Type check, lint, unit test, production build, route/error-state smoke tests.
- **Acceptance:** Clean build passes; all API types are explicit; shell works at mobile and desktop widths with keyboard-visible focus.
- **Evidence:** Commands/results and responsive screenshots tied to commit SHA.
- **Audit:** A7.

### [ ] T23 - Live Review Analyzer and Baseline Comparison UI

- **Depends on:** T06, T21, T22.
- **Owns:** Analyzer route, span highlighting, baseline comparison.
- **Instructions:** Build review input/analyze action, detected aspects, sentiment/confidence, normalized IDs, tags, and safe source-text highlighting from character offsets. Add the whole-review baseline versus proposed-system comparison. Include validation, keyboard operation, retry, no-aspect, and model-unavailable states. Render review text as text, never unsafe HTML.
- **Tests:** Multiple/repeated/non-overlapping spans, empty input, negation, no aspect, long input, API error/retry, keyboard flow, XSS payload.
- **Acceptance:** Highlighted text matches API offsets; color is not the only sentiment indicator; API failure preserves input; no unsafe HTML path exists.
- **Evidence:** Component/E2E results, console/network check, mobile/desktop screenshots.
- **Audit:** A7.

### [ ] T24 - Product Dashboard, Aspect Explorer, and Detail Drawer

- **Depends on:** T21, T22.
- **Owns:** Product insights UI.
- **Instructions:** Implement product selection/header, top customer tags, strengths/weaknesses, sortable/searchable aspect table, sentiment charts, representative reviews, and accessible detail drawer showing raw expressions and normalized aspect. Use real API contracts and non-color labels/icons.
- **Tests:** Sort/search, sparse/empty product, percentage/count fixtures, loading/error, drawer focus trap/restore, keyboard close, overflow at supported viewports.
- **Acceptance:** Displayed numbers match API fixtures; drawer is keyboard accessible; no overlap or horizontal overflow; representative evidence matches the selected aspect.
- **Evidence:** Tests, accessibility scan, screenshots, API fixture mapping.
- **Audit:** A7.

### [ ] T25 - Batch Upload and Model Metrics UI

- **Depends on:** T21, T22, T26 metrics schema.
- **Owns:** Upload/progress and metrics routes.
- **Instructions:** Build CSV/JSON upload with client-side type/size checks, real job polling, named processing stages, reload-safe job ID, completion/skipped/failure summary, and retry. Render model comparison charts only from committed machine-readable metrics; display `Not run` rather than inventing results.
- **Tests:** Invalid/oversized files, upload error, partial processing, polling recovery, route reload, missing metrics, accessible chart/table fallback.
- **Acceptance:** Progress represents backend state; charts match source metrics; invalid input is blocked with clear recovery.
- **Evidence:** Component/E2E tests, metric-to-chart reconciliation, screenshots.
- **Audit:** A7.

### [ ] T26 - Formal Evaluation and Error Analysis

- **Depends on:** T06, T09, T12, T14, T17.
- **Owns:** Reproducible academic evaluation artifacts.
- **Instructions:** Freeze held-out datasets and thresholds before evaluation. Generate extraction P/R/F1, sentiment accuracy/Macro-F1/per-class recall/confusion matrix, normalization accuracy, and end-to-end tag P/R/F1. Compare baselines, DistilBERT, and BERT only when actually run on identical splits. Categorize errors and record runtime/hardware.
- **Tests:** Metric functions against hand-calculated examples; rerun determinism; artifact schema validation; report-table generation from machine-readable results.
- **Acceptance:** All selected metric floors pass; every number traces to a command, data hash, seed, model revision, and checkpoint; test data was never used for tuning.
- **Evidence:** JSON/CSV metrics, plots, commands, environment, data/model cards, error report.
- **Audit:** A8, with relevant A2-A5 gates rerun when data/model artifacts changed.

### [ ] T27 - Docker, CI, and Reproducible Startup

- **Depends on:** T19, T21, T22.
- **Owns:** Containers, Compose, CI, operations instructions.
- **Instructions:** Add backend/frontend images and Compose services for PostgreSQL, API, and UI. Include health checks, migration startup, persistent DB volume, runtime model mounting/downloading, non-secret environment template, and CI for Python tests, frontend checks, migrations, and fixture smoke tests. Do not run expensive full training in CI or bake datasets/checkpoints/secrets into images.
- **Tests:** Clean image builds, `docker compose config`, service health, migration, API/UI smoke, restart/persistence, CI-equivalent commands.
- **Acceptance:** One documented command starts the fixture workflow; services become healthy; DB persists; images contain no secret/raw data/model checkpoint.
- **Evidence:** Build/start/smoke logs, image scan, CI run, configuration output.
- **Audit:** A8.

### [ ] T28 - Full-System Verification and Handoff

- **Depends on:** T18, T21, T23, T24, T25, T26, T27.
- **Owns:** Final documentation, demo evidence, release candidate.
- **Instructions:** From a clean clone, exercise product selection, dashboard, detail drawer, live review analysis, upload-to-results, metrics page, restart/persistence, and failure recovery. Verify desktop/mobile layout, keyboard access, console/network state, API/database consistency, and documentation commands. Add architecture, setup, training, inference, evaluation, dataset licensing, model limitations, and demo script documentation.
- **Tests:** Full E2E, accessibility scan, clean-start smoke, release secret/artifact scan, dependency audit, documentation command replay.
- **Acceptance:** All A0-A8 gates pass on the release SHA; zero Critical/High findings remain; every academic/product claim is backed by evidence; clean-machine fixture workflow succeeds.
- **Evidence:** Final audit register, E2E logs, screenshots, dependency reports, release SHA.
- **Audit:** A8.

## 6. Audit Gates

### [ ] A0 - Repository, Scope, and Contract Audit

Audit T00-T01. Verify tracked files, ignore rules, secret/raw-data/checkpoint absence, documented Python/Node versions, deterministic config, source-plan fidelity, schema completeness, label maps, offsets/confidences, and MVP non-goals. Run `git diff --check`, inspect `git ls-files`, and perform tracked-secret/artifact scans. Block later work for any provenance, secret, or shared-contract issue.

### [ ] A1 - Dataset Integrity and Leakage Audit

Audit T02-T05. Verify official sources/licenses/checksums, common-schema validation, conversion counts, rejected rows, offsets, conservative cleaning, immutable split manifests, exact-duplicate/product/source leakage, label distributions, privacy minimization, and Amazon inference-only use. Re-run golden conversions and adversarial preprocessing fixtures. Block training for any leakage or unreconciled data loss.

### [ ] A2 - Baseline and Aspect Extraction Audit

Audit T06-T09. Verify BIO/subword alignment, special/padding masking, span reconstruction, training/validation/test separation, validation-only checkpointing, seed/config capture, exact-span metrics, baseline comparison, checkpoint hash, and inference offsets. Run no-aspect, repeated, multiword, negated, and long-review cases. Require extraction F1 `>= 0.70` and baseline improvement.

### [ ] A3 - Aspect Sentiment Audit

Audit T06 and T10-T12. Verify pair construction, label mapping, aspect survival under truncation, leakage prevention, class balance handling, validation-only selection, probabilities, confusion matrix, per-class performance, and aspect-conditioned behavior. Require Macro-F1 `>= 0.65`, every class recall `>= 0.50`, and baseline improvement.

### [ ] A4 - Normalization, Tags, Aggregation, and Ranking Audit

Audit T13-T16. Verify ontology coverage/collisions, pinned MiniLM revision, cached embeddings, separated threshold tuning/held-out mappings, explicit unknown behavior, deterministic template coverage, exact aggregation arithmetic, configured minimum mentions, threshold boundaries, ranking formula, tie-breaking, Top-K bounds, representative-review correctness, and idempotency. Require held-out normalization accuracy `>= 0.80`.

### [ ] A5 - End-to-End ML and Batch Audit

Audit T17-T18. Verify the single reusable pipeline order, source offsets, confidence fields, models loaded once, empty/no-aspect/unknown behavior, model-load failures, frozen end-to-end evaluation, Amazon sampling provenance/privacy, batch resume, failure accounting, and duplicate prevention. Require end-to-end Tag F1 `>= 0.60` and correct output for `Amazing display but terrible battery.`

### [ ] A6 - Database, API, Security, and Privacy Audit

Audit T19-T21. Run migrations against a disposable DB; verify constraints, relationships, indexes, transactions, rollback, idempotency, upload/inference limits, CSV/JSON validation, pagination, error mapping, health/readiness, OpenAPI, restricted CORS, and public upload protection or explicit local-only binding. Test oversized, binary, malformed, duplicate, concurrent, path-like, formula-like, HTML/script, and unknown-product inputs. Block for raw traceback/secret exposure or state corruption.

### [ ] A7 - Frontend Contract, Visual, and Accessibility Audit

Audit T22-T25 against the real API. Verify dashboard/analyzer/upload/metrics workflows, contract consistency, real rather than fabricated data, loading/empty/error/offline states, responsive layout, text overflow, keyboard navigation, focus management, semantic forms/tables, accessible names, contrast, non-color sentiment cues, reduced motion, console/network errors, and stored/reflected XSS. Run unit/build/E2E and accessibility checks at mobile and desktop viewports.

### [ ] A8 - Release and Reproducibility Audit

Audit T26-T28. From a clean clone, build/start Compose, migrate the DB, analyze one review, ingest a batch fixture, generate/retrieve insights, render the dashboard, restart services, and verify persistence/recovery. Re-run metric generation from frozen artifacts and reconcile README/report/presentation claims. Scan dependencies, images, tracked files, and logs for secrets/high-severity risks. Pass only when A0-A8 are green on the release SHA with zero open Critical/High findings.

## 7. Remediation Loop

1. Auditor records a stable finding ID such as `A3-HIGH-001`, assigns severity/owner, and links affected downstream gates.
2. The original work agent fixes only the assigned issue and adds a regression test. It must not change frozen test data or thresholds unless the finding explicitly requires a reviewed methodology change.
3. Auditor confirms the fix did not remove or weaken tests, reruns the exact reproduction and relevant regression suite, and appends evidence while retaining the original failure.
4. Data/split changes invalidate A2-A5 metrics. Model/pipeline changes invalidate that gate and downstream ML/API/UI gates. Schema/API changes invalidate A6-A8. Security configuration changes rerun A6 and A8.
5. Close a finding only when the reproduction no longer fails and regression tests pass. After three failed remediation cycles, escalate to the root agent for architecture/requirements triage instead of lowering acceptance criteria.

## 8. Dependency and Audit Order

```text
T00 -> T01
T00 -> T02
T01 + T02 -> T03 + T04 -> T05
T05 -> T06
T01 + T05 -> T07 -> T08 -> T09
T01 + T05 -> T10 -> T11 -> T12
T05 -> T13 -> T14
T13 -> T15
T01 + T15 -> T16
T09 + T12 + T14 + T15 -> T17 -> T18
T01 -> T19
T16 + T17 + T18 + T19 -> T20 -> T21
T17 + T21 -> T22
T06 + T21 + T22 -> T23
T21 + T22 -> T24
T21 + T22 + T26 -> T25
T06 + T09 + T12 + T14 + T17 -> T26
T19 + T21 + T22 -> T27
T18 + T21 + T23 + T24 + T25 + T26 + T27 -> T28

A0 after T00-T01; A1 after T02-T05; A2 after T09; A3 after T12;
A4 after T16; A5 after T18; A6 after T21; A7 after T25; A8 after T28.
```

Safe parallel work is allowed only where the graph shows independent branches. No dependent task may begin while its required audit gate is `BLOCKED`.
