# Release status

Documentation reconciled: **2026-10-30**. The Vercel/Render demo and unpacked
Chrome extension are documented in the [hosting guide](render-demo.md) and
[extension guide](../frontend/extension/README.md). Remote CI must be checked
separately. The table below preserves the **2026-10-15** local verification record;
later scoped checks appear in [shopping companion](shopping-companion.md#verification-and-fixes)
and [Render demo](render-demo.md#verification-before-deployment). [Documentation index](README.md) · [Verification commands](verification.md)

## Current verification

| Check | Latest local evidence | Remaining boundary |
|---|---|---|
| Full Python suite | **326 passed, 2 skipped** | PostgreSQL migration/repository suites require `POSTGRES_TEST_URL` |
| Browser workflows | **20 passed** | Isolated heuristic API; provider responses injected for LLM UI checks |
| Frontend unit tests | **5 passed** | Includes Unicode and CRLF selection-offset checks |
| Frontend lint and build | Passed | Vite reports a bundle-size advisory; build succeeds |
| Responsive layout | Inspected at **320, 768, 1440 px** | Local Chromium checks |
| PostgreSQL migration SQL | Generated through **0005_review_annotations** | No live PostgreSQL execution on this host |
| Trained application smoke | Preview, correction, annotation, reload, and export passed | Temporary synthetic products; no accuracy estimate |
| Docker/Compose | Configuration previously validated | Container build/start and Linux dependency installation remain unverified here |
| Remote CI | Workflow configured | Check GitHub Actions separately for the pushed commit |

The full Python run includes verified trained-checkpoint tests and the HTTP →
worker → database → published-snapshot path. The non-model collection fix also
allows CI to collect tests without installed PyTorch/Transformers. Local results
do not certify the remote environment.

## Implemented workflows

| Area | Current behavior | Details |
|---|---|---|
| Trained analysis | Verified DistilBERT artifacts, frozen `full_review` policy, exact source evidence | [ML guide](ml-explained.md) |
| Durable processing | Transactional deduplication, idempotent submissions, leases, heartbeats, retries, restart recovery | [Architecture](architecture.md) |
| Published insights | Immutable versioned snapshots; evidence, totals, and revision remain consistent during processing | [Aggregation policy](contracts/aggregation.md) |
| Preview/import | Expiring unsaved previews, explicit save, bounded multi-format imports, row errors, draft/job recovery | [Getting started](getting-started.md) |
| Evidence tools | Robustness, quality queue, product comparison, snapshot/model-version checks | [Faculty demo](faculty-demo.md) |
| Optional LLM | User-requested suggestions and cited Q&A through Groq, Gemini, or Ollama | [LLM assistance](llm-assistance.md) |
| Corrections | Server-recorded suggestions; append-only accept/edit/reject decisions with provenance and export | [Review corrections](review-corrections.md) |
| Full-review annotation | Missing aspects, boundary edits, drafts, review status, next-item navigation, history, export | [Annotation workspace](review-annotations.md) |
| Data controls | Named imports, batch removal, clear reviews, product deletion, persistent one-time seeding | [Saved data](saved-data.md) |
| Dataset preparation | Versioned smart-device source, hash verification, overlap audit, development/held-out tasks | [Annotation workset](annotation-workset.md) |

Corrections and annotations remain separate from model outputs, aggregate totals,
ontology aliases, and training. New per-aspect decisions reopen completed reviews.
Reviewer names and completion are self-reported, not independently adjudicated
gold labels. The UI preserves failed/conflicting drafts until explicitly reloaded.

## Measured ML evidence

| Measurement | Recorded value |
|---|---:|
| Exact-span extraction F1 | 70.62% |
| Sentiment Macro F1, gold aspects | 74.96% |
| Sentiment accuracy, gold aspects | 82.49% |
| Neutral sentiment recall | 51.63% |

The trained `full_review` policy was selected on validation before the frozen
test evaluation. The explicit heuristic demo uses `local_clause` and is labeled
separately. The trained policy has a documented contrastive-sentence limitation.
See [evaluation](evaluation.md) and [performance](performance.md) for protocols,
split hashes, baseline limits, and raw evidence. No new ML accuracy is inferred
from the correction or annotation features.

## Dataset and review evidence

The downloaded Virtual Assistant Devices workbook contains **2,370 reviews**.
After grouping duplicates and excluding one normalized training-text overlap,
**2,338 groups** are eligible. Preparation produced 100 development and 100
held-out tasks. The development transformer run produced 180 mentions, including
156 unknown mappings; these are diagnostic counts, not error rates.

An automated source-text review produced 204 proposed explicit mentions across
the development tasks. All 100 remain pending independent human review, and the
held-out set remains unscored. Source labels describe whole-review sentiment and
categories, not the missing span/canonical-ID/per-mention gold labels. Original
workbook labels are preserved despite a published-count discrepancy. The
[workset guide](annotation-workset.md) records selection, provenance, and limits.

## Quality gates still open

| Gate | Evidence still needed |
|---|---|
| Normalization calibration | A pinned local semantic model, reviewed development threshold, and reviewer/adjudication provenance |
| End-to-end tag quality | Representative independent labels for spans, canonical IDs including unknowns, and per-mention sentiment |
| Held-out evaluation | Finish annotation and development decisions, freeze the candidate pipeline/ontology, then evaluate untouched held-out data |
| LLM quality | Representative suggestion/answer evaluation; citation existence alone does not prove interpretation |
| Deployment | Live PostgreSQL checks, Linux lock/install verification, clean Compose build/start, persistence/recovery checks |
| Public service | Authentication/authorization and an operational deployment plan |

Only 77 of 309 existing validation normalization labels map to the current
ontology, so scoring that subset would not establish complete tag quality.
Semantic normalization remains off by default. The checked-in dependency lock
records a macOS ARM64 resolution; it is not Linux installation evidence.

## Smoke checks and their limits

The running trained app passed synthetic preview, correction and full-review
annotation checks, including browser save, status filtering, reload and JSON
export. Product detail stayed identical after reviewer writes, and temporary
test products were removed. These checks validate integration, not annotation
correctness or production load.

A ten-sample warm preview run on Apple M4 recorded **566.45 ms median** completion,
including scheduling and polling. It is not a throughput or production latency
claim. Live Groq mapping/Q&A smoke checks previously passed with exact quote
validation; a Gemini check returned provider HTTP 503. Injected-provider tests
and connectivity checks do not establish representative LLM accuracy.

New snapshots record explicit review membership. Older snapshots use an analysis
creation-time compatibility cutoff; reprocessing creates explicit membership.
All current PostgreSQL schema changes are available through Alembic head (0005).
