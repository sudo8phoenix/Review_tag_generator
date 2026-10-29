# Documentation

Choose a starting point below. The guides describe implemented behavior; the
API v1 design contract is explicitly separated from the current runtime API.

## Start and operate

| Guide | Use it for |
|---|---|
| [Getting started](getting-started.md) | Installation, ports, local models, Compose, troubleshooting |
| [Chrome extension installation](../frontend/extension/README.md) | Source locations, build/load, hosted/local connections, permissions, recovery |
| [Shopping companion](shopping-companion.md) | Design references, saved-product UI, unpacked Chrome setup, checks, and boundaries |
| [Current API reference](api.md) | Live routes, payloads, polling, review writes, and exports |
| [Verification](verification.md) | Reproducible Python, frontend, browser, and migration checks |
| [Release status](release-status.md) | Current verification, evidence gates, and deployment limits |
| [Saved-data controls](saved-data.md) | Import removal, clearing reviews, deletion, and storage behavior |

## Review and annotate

| Guide | Use it for |
|---|---|
| [LLM assistance](llm-assistance.md) | Provider configuration, unknown-aspect suggestions, cited answers |
| [Reviewer corrections](review-corrections.md) | Accept/edit/reject, sentiment corrections, history, decision export |
| [Annotation workspace](review-annotations.md) | Missing spans, boundary edits, progress filters, drafts, annotation export |
| [Review quality queue](review-quality.md) | Understand prioritization signals and prediction-evidence exports |
| [Evidence robustness](evidence-robustness.md) | Interpret single-review-removal sensitivity |
| [Product comparison](product-comparison.md) | Understand support checks and compatible pipeline comparisons |

## Models, data, and evaluation

| Guide | Use it for |
|---|---|
| [ML implementation](ml-explained.md) | Models, training, inference, rules, and limitations |
| [Evaluation methodology](evaluation.md) | Frozen splits, protocol selection, component metrics, error exports |
| [Measured performance](performance.md) | Evidence-backed ML, preview timing, and verification claims |
| [Winning model record](winning-model.md) | Original checkpoint configuration and recorded hashes |
| [Normalization](normalization.md) | Alias policy, optional semantic matching, calibration gates |
| [Dataset sources](datasets.md) | Source terms, local downloads, Amazon sampling/import |
| [Annotation workset](annotation-workset.md) | Smart-device workbook audit, task preparation, automated proposals |

## Architecture and reference contracts

| Guide | Status |
|---|---|
| [System architecture](architecture.md) | Implemented browser/API/worker/database and reviewer flows |
| [Aggregation contract](contracts/aggregation.md) | Implemented saved-analysis voting and ranking policy |
| [API v1 design contract](contracts/api-v1.md) | Target DTO/fixture design; not the live route table |

## Hosting

- [Render demo](render-demo.md): current Vercel/Render topology, free-tier limits, and health checks.
- [Oracle alternative](free-hosting.md): historical setup attempt and an alternative deployment recipe.

## Demonstration and portfolio

- [Faculty demonstration](faculty-demo.md): a repeatable synthetic-data walkthrough.
- [Portfolio guide](portfolio-guide.md): product explanation, contributions, and defensible claims.
- [Screenshot assets](assets/portfolio/README.md): actual UI captures with source/test provenance.

Current verification counts live in [release status](release-status.md).
Frozen model scores remain in [evaluation evidence](../audit/evidence/current/test.json).
Local reviews, exports, raw datasets, credentials, and databases are not part of
the published documentation bundle.
