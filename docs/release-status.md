# Release status

The application now uses the same frozen `full_review` policy for trained inference
as the recorded evaluation. Startup verifies the frozen validation hash. The
explicit heuristic demo uses `local_clause` and is reported separately.

## Implemented

- Snapshot-consistent review evidence, totals and published revision during imports.
- Live previews serviced between bulk rows with the bulk lease renewed.
- API startup without model loading when a separate worker is configured.
- [Evidence robustness audit](evidence-robustness.md) API with single-review-removal
  sensitivity, tag stability, and separate within-review contradiction counts.
- [ML implementation guide](ml-explained.md) covering models, training, inference,
  evaluation, application rules, and limitations.
- One SQLAlchemy repository for PostgreSQL deployment and SQLite local use.
- Durable jobs and item progress, transactional duplicate prevention, idempotent
  requests, bounded automatic retries, manual failed-row retries, expiring leases,
  worker heartbeats, restart recovery, and immutable versioned aggregate snapshots.
- Expiring, unsaved previews processed by workers; separate saving; browser draft
  and job recovery; preserved input after partial failures.
- Aspect highlighting, evidence drawers with normalization and sentiment evidence,
  searchable/sortable insights, sentiment charts, representative reviews, and
  recorded evaluation scores with provenance.
- Validated TXT, CSV, JSON, JSONL and NDJSON imports, background progress, complete
  row-error downloads, resumable Amazon batch import, and a read-only legacy demo
  migration helper. See [dataset instructions](datasets.md).
- Complete extraction and sentiment error exports from the frozen test run:
  [manifest](../audit/evidence/current/error-exports/test/manifest.json).
- API/storage/worker tests, trained inference integration tests, PostgreSQL-specific
  integration tests, browser workflow checks, CI, and a Compose deployment stack.

## Verification on this workspace

The full Python suite passes (254 passed, 2 PostgreSQL suites skipped), including
trained checkpoint tests and the complete
HTTP → worker → database → snapshot path. PostgreSQL migration and repository
integration tests require `POSTGRES_TEST_URL`; they are configured to run against
an isolated PostgreSQL service in CI. The generated PostgreSQL migration SQL was
checked locally. Frontend lint, production build, and unit tests pass; all 12
Playwright browser tests pass, including the complete preview/save flow and draft
recovery. Layouts were checked at 320, 768, and 1440 pixels without console or page
errors. Compose configuration validation succeeds.

The local environment has no accessible PostgreSQL server or Docker daemon, so
live PostgreSQL tests and container builds have not been executed here. The
checked-in Python lock records a macOS ARM64 resolution; Linux container
installation still needs verification. CI configuration is provided, but no
remote CI run or deployment has been triggered by this task.

## Quality gates still requiring real evidence

Semantic matching is implemented and can be configured with `SEMANTIC_MODEL_PATH`,
`SEMANTIC_MODEL_REVISION`, and `NORMALIZATION_THRESHOLD` for both API and worker.
The API and worker must receive the same settings. Alias matching remains the
default until a pinned local MiniLM snapshot and a reviewed threshold are supplied.
There is no approved human-reviewed calibration artifact. Synthetic fixture
accuracy is development evidence only. See [normalization](normalization.md).

End-to-end canonical tag accuracy cannot be claimed from the current annotations:
only 77 of 309 validation normalization labels map to this ontology. A representative,
human-reviewed set with aspect spans, canonical IDs (including unknowns), and
sentiment is needed. Reviewers must settle ambiguous labels, document adjudication,
select a threshold using development rows, and review the untouched held-out gate.
The application does not display an invented release-quality score.

The frozen `full_review` policy meets the recorded dataset-level gates but has a
known contrastive-sentence limitation, documented in [evaluation](evaluation.md).

## Recent verification update

The Python suite was rerun after the scheduling, snapshot, external-worker startup,
and evidence-audit changes. Regression checks cover intermediate import state,
previews arriving during bulk inference, API startup without model construction,
and robustness threshold boundaries. These backend changes do not constitute a
new browser or live PostgreSQL verification run.

New snapshots record exact review membership. For snapshots created before this
change, evidence selection uses the snapshot creation timestamp as a compatibility
fallback. Reprocessing saved reviews publishes a snapshot with explicit membership.

## Faculty demonstration features

The product insights dashboard now includes interactive evidence robustness,
a review quality queue with JSON export, and support-aware product comparison.
Comparison suppresses directional results when pipeline versions differ. Queue
and robustness views check snapshot identity before displaying results. See the
[faculty demo guide](faculty-demo.md) for contribution details and examples.

The GitHub non-model collection failure was fixed by moving the optional PyTorch
import into the model test that uses it. The non-model suite was checked locally
with both `torch` and `transformers` imports blocked. This follow-up does not
constitute evidence of a completed remote GitHub Actions run.

## Optional assistance follow-up

Unknown-aspect suggestions and product-review Q&A are implemented with structured
outputs and server-side source validation. Groq, Gemini and Ollama are configurable;
secrets stay in ignored server configuration. See [LLM assistance](llm-assistance.md).
The full Python suite passes with 254 tests and 2 PostgreSQL skips. Provider transport,
evidence rejection, and no-write behavior are verified using injected test responses.
Live Groq smoke verification now passes with server-side credentials. A live Gemini request
returned provider HTTP 503 due to high demand.

The full 12-test browser suite passes after the assistance integration, using an
isolated heuristic API plus explicitly injected provider responses for assistant
UI tests. Frontend lint, production build, and unit tests pass. The non-model
Python command passes with 247 tests, 2 PostgreSQL skips and 7 model deselections.


Groq live follow-up: synthetic unknown-aspect mapping and two-review Q&A both
succeeded, with source quote validation. Added an application User-Agent header
after the provider edge rejected the default Python client with error 1010.
All 11 provider transport regression tests pass. These smoke checks do not
establish statistical accuracy for the optional assistance layer.
