# Shopping implementation audit index

Date: 27 October 2026. See [implementation report](shopping-companion.md) for fixes and final check results.

All endpoints share the existing **unauthenticated, local single-user** boundary. There is no account/tenant authorization flow to test. Local source/tests are the verification scope below; public hosting, live PostgreSQL interleavings, real provider transport, load testing, and live-retailer variation remain unverified. No production/paid requests or user-data removal were performed.

## Table 1. API endpoints

| ID | Method / path | Caller | Input / source | Response, preconditions, side effects | Mark / evidence |
|---|---|---|---|---|---|
| A1 | GET `/api/health` | ModelsPage, extension connection, launcher | `none`; `main.py:120` | Read DB and worker heartbeat; health metadata | verified — local source + test_application.py |
| A2 | GET `/api/ready` | operational readiness/test callers | `none`; `main.py:130` | Read health; 503 without live compatible worker | verified — local source + test_application.py |
| A3 | GET `/api/demo/products` | ProductsPage, ComparePage, comparison panel, extension | `none`; `main.py:138` | Read product catalog/counts | verified — local source + test_application.py |
| A4 | POST `/api/demo/products` | ProductsPage, extension product form | `body: ProductInput`; `main.py:143` | Validate name; insert empty product | verified — local source + test_application.py |
| A5 | GET `/api/demo/products/{product_id}` | ProductDetail, library/API consumers | `product_id: str`; `main.py:148` | Read consistent published snapshot and evidence | verified — local source + test_application.py |
| A6 | DELETE `/api/demo/products/{product_id}/saved-data` | SavedDataControls | `product_id: str`; `main.py:156` | Reject active work; remove dependent data; publish empty snapshot | verified — local source + test_application.py |
| A7 | DELETE `/api/demo/products/{product_id}` | SavedDataControls | `product_id: str`; `main.py:161` | Reject active work; delete selected product/dependents | verified — local source + test_application.py |
| A8 | GET `/api/demo/products/{product_id}/imports` | SavedImportsPanel | `product_id: str`; `main.py:166` | Read named imports for product | verified — local source + test_application.py |
| A9 | DELETE `/api/demo/products/{product_id}/imports/{job_id}` | SavedImportsPanel | `product_id: str, job_id: UUID`; `main.py:171` | Check batch ownership/active work; remove owned inserted reviews; republish | verified — local source + test_application.py |
| A10 | GET `/api/assist/status` | ReviewAssistant | `none`; `main.py:199` | Read provider status without API keys | verified — local source + test_application.py |
| A11 | POST `/api/assist/normalize` | UnknownAspectAssist | `body: AspectAssistInput`; `main.py:205` | Validate exact span; bounded optional provider request; ephemeral suggestion | verified — local source + test_application.py; live provider unverified |
| A12 | POST `/api/demo/products/{product_id}/ask` | ProductReviewAssistant | `product_id: str, body: ProductQuestionInput`; `main.py:215` | Retrieve saved excerpts; bounded optional provider request; validate cited quotes | verified — local source + test_application.py; live provider unverified |
| A13 | GET `/api/demo/products/{product_id}/evidence-audit` | EvidenceRobustnessPanel | `product_id: str`; `main.py:225` | Read published votes; single-removal analysis | verified — local source + test_application.py |
| A14 | GET `/api/demo/products/{product_id}/quality-queue` | ReviewQualityPanel | `product_id: str`; `main.py:233` | Read published predictions; advisory ranking | verified — local source + test_application.py |
| A15 | GET `/api/corrections/options` | AspectCorrectionPanel, annotation workspace | `none`; `main.py:241` | Read ontology IDs/labels | verified — local source + test_corrections.py |
| A16 | GET `/api/demo/products/{product_id}/corrections/history` | AspectCorrectionPanel | `product_id: str, snapshot_id: UUID, review_id: UUID, start_char: int, end_char: int`; `main.py:249` | Check product/snapshot/review/span; read decision history | verified — local source + test_corrections.py |
| A17 | GET `/api/demo/products/{product_id}/corrections` | CorrectionExport | `product_id: str`; `main.py:257` | Check product; read original evidence and append-only decision log | verified — local source + test_corrections.py |
| A18 | POST `/api/demo/products/{product_id}/corrections` | AspectCorrectionPanel | `product_id: str, body: CorrectionInput`; `main.py:262` | Check snapshot/span/revision/request ID; append decision without changing model totals | verified — local source + test_corrections.py |
| A19 | POST `/api/demo/products/{product_id}/corrections/suggest` | AspectCorrectionPanel | `product_id: str, body: MentionReference`; `main.py:267` | Validate unknown span; optional provider call; recheck snapshot before saving suggestion | verified via local source + test_corrections.py; live provider unverified |
| A20 | GET `/api/demo/products/{product_id}/compare/{other_product_id}` | ProductComparisonPanel | `product_id: str, other_product_id: str`; `main.py:281` | Read two snapshots; support/version gates; no inference | verified — local source + test_application.py |
| A21 | GET `/api/demo/products/{product_id}/annotations` | ReviewAnnotationWorkspace | `product_id: str, snapshot_id: UUID / None=None, status: Literal['all', 'needs_review', 'reviewed', 'needs_adjudication']='all'`; `main.py:290` | Read snapshot-pinned worklist and effective status | verified — local source + test_annotations.py |
| A22 | POST `/api/demo/products/{product_id}/annotations` | ReviewAnnotationWorkspace | `product_id: str, body: AnnotationInput`; `main.py:296` | Check exact spans/canonical labels/revision/request ID; append annotation | verified — local source + test_annotations.py |
| A23 | GET `/api/demo/products/{product_id}/annotations/export` | ReviewAnnotationWorkspace | `product_id: str, snapshot_id: UUID`; `main.py:301` | Check snapshot; export latest saved revisions/effective status | verified — local source + test_annotations.py |
| A24 | GET `/api/demo/products/{product_id}/annotations/{review_id}` | ReviewAnnotationWorkspace | `product_id: str, review_id: UUID, snapshot_id: UUID`; `main.py:306` | Check product/snapshot/review; read draft/history | verified — local source + test_annotations.py |
| A25 | POST `/api/demo/products/{product_id}/preview` | ReviewForm, extension | `product_id: str, body: ReviewsInput`; `main.py:311` | Bound queue/input; insert expiring unsaved previews | verified — local source + test_application.py |
| A26 | POST `/api/demo/products/{product_id}/preview-summary` | extension preview poll | `product_id: str, body: PreviewSummaryInput`; `main.py:331` | Check preview product/version/status/expiry; dedup; aggregate without writes | verified — local source + test_application.py; new expiry/version/product/dedup checks |
| A27 | GET `/api/demo/previews/{preview_id}` | ReviewForm, extension | `preview_id: UUID`; `main.py:337` | Check ID/expiry; read temporary status/analysis | verified — local source + test_application.py |
| A28 | POST `/api/demo/products/{product_id}/jobs` | ReviewForm, extension, importer scripts | `product_id: str, body: ReviewsInput, idempotency_key: str / None=Header(default=None)`; `main.py:364` | Validate bounded reviews; dedup and idempotent durable enqueue | verified — local source + test_application.py |
| A29 | POST `/api/demo/products/{product_id}/reviews` | ReviewForm, extension, importer scripts | `product_id: str, body: ReviewsInput, idempotency_key: str / None=Header(default=None)`; `main.py:364` | Validate bounded reviews; dedup and idempotent durable enqueue | verified — local source + test_application.py |
| A30 | POST `/api/demo/imports/validate` | ReviewForm, importer | `body: ImportInput`; `main.py:370` | Bound/parse input; report row errors without saving | verified — local source + test_application.py |
| A31 | POST `/api/demo/products/{product_id}/imports` | ReviewForm, importer | `product_id: str, body: ImportInput, idempotency_key: str / None=Header(default=None)`; `main.py:379` | Bound/parse input; enqueue accepted rows and validation errors | verified — local source + test_application.py |
| A32 | POST `/api/demo/products/{product_id}/regenerate` | ProductDetail | `product_id: str`; `main.py:388` | Reuse active regeneration or enqueue missing-version reviews | verified — local source + test_application.py |
| A33 | GET `/api/demo/jobs/{job_id}` | ReviewForm, extension, importer | `job_id: UUID`; `main.py:394` | Read job progress and row errors | verified — local source + test_application.py |
| A34 | POST `/api/demo/jobs/{job_id}/retry` | ReviewForm, extension | `job_id: UUID`; `main.py:399` | Require terminal failure; requeue failed rows only | verified — local source + test_application.py |
| A35 | GET `/api/demo/jobs/{job_id}/errors.csv` | ReviewForm, extension, importer | `job_id: UUID`; `main.py:404` | Read errors; escape formula-like cells; download CSV | verified — local source + test_application.py |
| A36 | GET `/api/models/metrics` | ModelsPage | `none`; `main.py:416` | Read named frozen evaluation JSON files | verified — local source + test_application.py |

## Table 2. State machines
| ID | Entity / source | Verification |
|---|---|---|
| S1 | Products loading/create/search — routes/pages.tsx ProductsPage | verified — local source + relevant unit/integration/browser suite |
| S2 | Product selection/feature vote filters — ProductInsights.tsx | verified — local source + relevant unit/integration/browser suite |
| S3 | Review preview/save/retry/draft — routes/pages.tsx ReviewForm | verified — local source + relevant unit/integration/browser suite |
| S4 | Imports validation/file/preview/save — ReviewForm | verified — local source + relevant unit/integration/browser suite |
| S5 | Snapshot refresh/stale display — ProductDetail | verified API snapshot/regeneration behavior and effect cleanup source; browser regeneration interaction unverified |
| S6 | Comparison selection — ComparePage / ProductComparisonPanel | verified — local source + relevant unit/integration/browser suite |
| S7 | Correction suggestion/decision/revision — AspectCorrectionPanel / corrections.py | verified — local source + relevant unit/integration/browser suite |
| S8 | Annotation drafts/completion/conflict — ReviewAnnotationWorkspace / annotations.py | verified — local source + relevant unit/integration/browser suite |
| S9 | Clear/delete/remove-import — SavedDataControls / SavedImportsPanel | verified — local source + relevant unit/integration/browser suite |
| S10 | Optional assistant status/request/citations — ReviewAssistant / llm_assistance.py | verified via mocked-provider UI and grounding suites; real provider transport unverified |
| S11 | Durable queued/running/terminal jobs and leases — repository.py / worker.py | verified — local source + relevant unit/integration/browser suite |
| S12 | Extension capture/preview/summary/save/recovery — CompanionPanel.tsx | verified via actual Chrome/API paste, preview, save recovery and controlled tab-discovery race; selected/retailer live-page capture unverified |

## Table 3. Timers and background work
| ID | Entity / source | Verification |
|---|---|---|
| T1 | Review preview polling and cleanup — ReviewForm | verified — local source + relevant unit/integration/browser suite |
| T2 | Saved job polling and cleanup — ReviewForm | verified — local source + relevant unit/integration/browser suite |
| T3 | Regeneration polling — ProductDetail | unverified live UI interaction; source cleanup and API regeneration tests inspected |
| T4 | Worker leases, heartbeats, retries and shutdown — worker.py / repository.py | verified — local source + relevant unit/integration/browser suite |
| T5 | Extension polling/navigation invalidation — extension panel | verified — real Chrome/storage/API plus controlled tab-discovery race; live retailer unverified |

## Table 4. Numeric values
| ID | Entity / source | Verification |
|---|---|---|
| N1 | Reviews: 1–100, 1–10000 code points — main.py ReviewsInput | verified — local source + relevant unit/integration/browser suite |
| N2 | Imports: 10 MiB, 5000 rows; request body 12 MiB — imports.py / main.py | verified — local source + relevant unit/integration/browser suite |
| N3 | Preview queue capacity, TTL, lease/retry counts — repository.py / worker.py | verified — local source + relevant unit/integration/browser suite |
| N4 | Aspect offsets, counts, scores and vote thresholds — schemas.py / aggregation.py | verified — local source + relevant unit/integration/browser suite |
| N5 | Annotation/correction revisions and span boundaries — annotations.py / corrections.py | verified — local source + relevant unit/integration/browser suite |
| N6 | Extension ports/capture bounds/preview limit — extension settings/capture | verified — local source + relevant unit/integration/browser suite |

## Table 5. Data flows
| ID | Entity / source | Verification |
|---|---|---|
| F1 | Capture → preview → batch summary → explicit save → publish → web | verified — local source + relevant unit/integration/browser suite |
| F2 | Import → validate → preview → save → row error export | verified — local source + relevant unit/integration/browser suite |
| F3 | Saved feature → original quote → correction → history/export | verified — local source + relevant unit/integration/browser suite |
| F4 | Annotation draft → explicit completion → conflicts/export | verified — local source + relevant unit/integration/browser suite |
| F5 | Product/batch deletion → dependent records/snapshot/local drafts | verified — local source + relevant unit/integration/browser suite |
| F6 | Optional LLM request → provider → validated citation or suggestion | verified via mocked provider/grounding suites; live provider transport unverified |

## Table 6. Resource ledger
| ID | Entity / source | Verification |
|---|---|---|
| R1 | Product/review rows; dedup inflow, remove batch/clear/delete outflow — repository.py | verified — local source + relevant unit/integration/browser suite |
| R2 | Queue slots, previews and TTL — main.py / repository.py | verified — local source + relevant unit/integration/browser suite |
| R3 | Review votes/tag support — aggregation.py; corrections kept separate | verified — local source + relevant unit/integration/browser suite |
| R4 | Annotation progress/status — annotations.py | verified — local source + relevant unit/integration/browser suite |
| R5 | Paid transactions, entitlement balances | not applicable — no such feature |

## Table 7. Concurrency hotspots
| ID | Entity / source | Verification |
|---|---|---|
| C1 | Idempotent submit + per-product normalized-text dedup — repository.py | verified in SQLite/source; live PostgreSQL concurrency unverified |
| C2 | Preview/job claim/renew/finish ownership — repository.py | verified in SQLite/source; live PostgreSQL skip-locked behavior unverified |
| C3 | Snapshot publish vs delete/regenerate — repository.py | verified in SQLite/source; live PostgreSQL interleavings unverified |
| C4 | Correction/annotation expected revision + product lock — corrections.py / annotations.py | verified via local stale-revision/source checks; simultaneous PostgreSQL writers unverified |
| C5 | Stale frontend fetches and route/product replacement — page hooks and ComparePage | verified — local source + relevant unit/integration/browser suite |
| C6 | Extension page/settings/capture replacement vs in-flight preview/save — extension panel | verified — real Chrome/storage/API plus controlled tab-discovery race; live retailer unverified |


## Supplemental code-derived rows

| Table / ID | Source and entity | Mark / evidence |
|---|---|---|
| 2 / S13 | llm_provider.py:20 — one generation semaphore, acquire/release | verified via provider busy/release unit tests; external transport unverified |
| 3 / T6 | llm_provider.py:49 — bounded 1–120 second request timeout, 1 MiB response cap | verified via config/transport mocks; real provider timing unverified |
| 4 / N7 | llm_assistance.py — excerpt, question, source span and citation budgets | verified via grounding/invalid-citation unit tests |
| 6 / R6 | llm_provider.py:20 — optional provider concurrency slot | verified via busy/error/release tests; no paid calls |

## Adversarial pass

- Auth bypass: current runtime has no login or tenant roles. Local-only boundary and extension loopback restrictions are retained. A public/multi-user authorization assessment is unverified and outside this deployment mode.
- Injection: React text rendering, exact Unicode evidence spans, parameterized ORM access, bounded parsers, CSV error escaping, no source-driven fetch URLs or executable content in extension; local malformed-input/citation and hostile-host tests passed.
- Rate/resource abuse: input, upload, preview queue, provider concurrency, and response/time bounds traced and covered locally; no production load probes or storage-retention certification.
- Data leakage: provider status avoids secrets, capture is explicit, extension state stays in its local storage and configured local API; data sharing/tenant isolation for a hosted service remain unverified.
- Concurrency: replay after a lost actual API response is checked in Chrome; stale tab discovery is controlled in that test; stale reviewer revisions, lease recovery, deletion guards and published snapshots have local tests. PostgreSQL interleavings remain unverified.
- Dashboard/API chains: capture/import → preview → save → published evidence → correction/annotation → export/removal followed through current APIs and browser tests. Games, bots, WeChat, money/entitlement and external webhook chains are not applicable.

## Residual boundary

The seven tables are an index of the inspected local application paths, not an exhaustive production assessment. Trained-model performance was not re-evaluated. Live PostgreSQL/migrations, Linux containers/CI execution, real retailer UI variants, provider transport, account synchronization, and store publication remain unverified. Dependency advisory results are recorded in the implementation report.
