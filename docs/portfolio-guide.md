# Portfolio guide

This page is a portfolio-ready description of the project, its measured results,
and a practical demonstration plan. Pair it with the [architecture guide](architecture.md)
and the source-linked [ML guide](ml-explained.md).

## Hero copy

**Title:** Review Tag Generator

**Tagline:** Turn product reviews into feature-level feedback you can inspect.

**Short summary:**

> Review Tag Generator turns customer reviews into feature-level product insights. Two fine-tuned DistilBERT models identify aspects and their sentiment; deterministic rules normalize and aggregate predictions. Source spans, review-level support, versioned snapshots, and review tools make each result easier to inspect.

## Case study

**Case-study copy:**

> Product teams receive reviews but lack a view of which features people discuss and how they feel. Whole-review sentiment hides mixed opinions, while untraceable summaries make insights hard to verify. I worked on Review Tag Generator, a web application that identifies aspect spans, classifies sentiment for each aspect, maps known aliases to a shared ontology, and builds product summaries from saved reviews. The interface links tags back to source text and provides quality, comparison, and single-review-removal tools. Processing runs through durable jobs and publishes versioned snapshots so imports do not expose partial totals. Held-out scores measure extraction and sentiment separately; they are not an end-to-end tag accuracy claim. The system remains a portfolio demo, with evaluation and production limits documented.

The first-person wording is a template. Edit it to match your actual role and
contributions before publishing. This repository does not record individual
authorship or establish which parts were completed by one person or a team.

## The problem and user benefit

Whole-review sentiment compresses mixed feedback into one label. A review can
praise a display and criticize battery life in the same sentence. Product teams
need to know which feature is being discussed, connect the label to its evidence,
and distinguish repeated mentions from independent reviewer support.

| Audience | Need | Product benefit |
|---|---|---|
| Product manager or researcher | Find recurring strengths, weaknesses, and evidence gaps | Canonical feature summaries with review counts and representative evidence |
| Support or quality analyst | Trace an insight to the wording that produced it | Original-text spans, sentiment context, and a review quality queue |
| Evaluator or reviewer | Understand how much a tag depends on individual votes | Single-review-removal sensitivity results and snapshot provenance |
| Engineer or data scientist | Reproduce and inspect model behavior | Saved evaluation artifacts, explicit model modes, and versioned outputs |

## What makes this project distinctive

The useful distinction is the evidence and product layer around aspect-based
sentiment analysis. A basic sentiment demo returns one positive or negative label
for a whole review. This project extracts individual feature mentions, classifies
sentiment in relation to each aspect, maps aliases to canonical features, and
retains source offsets and context. Aggregation gives each review at most one vote
per aspect, records within-review contradiction as neutral evidence, and requires
three distinct supporting reviews before a product tag appears.

The application also addresses operational and analytical questions: previewing
does not change totals; saved jobs are durable; product pages read published
snapshots; a robustness report shows the effect of removing a review; a quality
queue prioritizes cases to inspect; and comparison suppresses a directional result
when support or pipeline compatibility is inadequate. These are implementation
and product-design contributions built around established models and methods. The
project does not claim a new model architecture or a new leave-one-out algorithm.

## Features to show

| Feature | What to demonstrate | Why it matters |
|---|---|---|
| Aspect-level analysis | Preview extracted phrases and sentiment before saving | One review may contain multiple feature opinions |
| Evidence drawer | Open a result and inspect the highlighted phrase and sentiment context | Makes model output traceable to original text |
| Product insights | Show canonical aspect support, sentiment mix, and representative reviews | Summarizes saved predictions while preserving evidence |
| Review quality queue | Inspect unknown aspects, low-confidence cases, empty detections, or contradictions | Helps a human decide what to review; it does not relabel predictions |
| Reviewer corrections | Save a separate category/sentiment decision and inspect history | Preserves the original model output and reviewer rationale |
| Full-review annotations | Add missed spans, edit boundaries, remove false detections, and track completion | Supports complete-review labeling, including explicit empty annotations |
| Evidence robustness | Remove a represented vote and observe classification and tag stability | Reveals sensitivity to the available review sample |
| Product comparison | Compare shared features and support across two products | Shows evidence gaps and avoids incompatible directional comparisons |
| Batch import and job controls | Validate/import a file, watch row progress, inspect errors, and manage saved data | Makes bulk workflows observable and recoverable |
| Optional LLM assistance | Request an unknown-aspect suggestion or ask a question with cited review excerpts | Adds an explicitly user-triggered aid without replacing the measured ML pipeline |

Batch controls are part of the application workflow. Check [release status](release-status.md)
for the current integration and verification record before describing their latest
UI details.

## Results and claims

The frozen held-out evaluation reports **0.706179 exact-span F1** for aspect
extraction and **0.749563 Macro F1 / 0.824913 accuracy** for sentiment on gold
aspect–sentiment pairs. The extraction score measures exact aspect boundaries;
the sentiment scores do not include extraction or ontology errors. Do not present
these figures as end-to-end product-tag accuracy. The documented baselines are
reported in the source evaluation but were not independently rerun in this work.
See [evaluation methodology and evidence](evaluation.md) and the [model guide](ml-explained.md).

Do not claim user counts, business impact, production deployment, a live public
service, or novel model training architecture from this repository. The current
application has no authentication and is intended as a local or trusted-network
demo. Container and remote CI checks are not established as passing by local
documentation alone. A measured ten-sample local smoke run recorded 566.45 ms median preview
completion on an Apple M4. This includes queue and polling overhead and is not
a production load test. See [performance and evidence](performance.md) for
protocols, raw timings, and the limits of that measurement.

## Demo flow and suggested captures

Use [the faculty demonstration guide](faculty-demo.md) for a repeatable synthetic
workflow. Prefer synthetic examples for a public portfolio capture; do not expose
private customer reviews or API credentials. A concise walkthrough is:

1. Open the product workspace and create or select a demo product.
2. Enter a review with two feature opinions. Preview it and explain that preview
   results are temporary and product totals have not changed.
3. Expand aspect evidence to show the original phrase, sentiment context, and
   normalization result.
4. Save the review, wait for the job to finish, then open product insights.
5. Show the quality queue, evidence robustness panel, and product comparison.
   Explain that each operates on saved predictions and published snapshots.
6. Open the annotation workspace, add or revise a span, save a draft, and show
   reviewed progress and export. Explain that these records do not update totals.
7. Optionally request LLM assistance. Show the returned source citation and state
   that it is user-triggered, optional, and separate from recorded model metrics.

Ready-to-use [screenshot assets and their provenance](assets/portfolio/README.md)
are included. Recommended portfolio screenshots, captured from the actual running UI:

| Capture | Suggested caption |
|---|---|
| Product insights with feature support and sentiment counts | “Review-level aspect votes become inspectable product summaries.” |
| Review preview with highlighted spans and evidence drawer | “Each prediction points back to its phrase and context in the source review.” |
| Evidence robustness panel | “Single-review-removal scenarios show when a tag depends on thin evidence.” |
| Review quality queue and exported evidence | “The queue prioritizes cases for human inspection without changing model labels.” |
| Product comparison with evidence gap visible | “Directional comparisons require minimum support and matching pipeline versions.” |
| Annotation editor and review progress | “Reviewer revisions preserve original predictions and exact source spans.” |
| Correction drawer and decision history | “Mapping and sentiment decisions are recorded separately with a reason.” |
| Import progress with validation feedback | “Bulk reviews move through a durable job with visible row-level outcomes.” |

Only use a screenshot if the displayed build and state match the caption. Do not
imply that illustrative or synthetic data are real customer evidence.

## Technical highlights

- Two separately fine-tuned DistilBERT checkpoints: token-level aspect extraction
  and aspect-conditioned three-class sentiment classification.
- Exact source spans, context offsets, confidence components, model backend, and
  pipeline provenance flow into saved evidence.
- Deterministic ontology aliases and tag templates keep normal output repeatable;
  semantic matching is optional and gated on reviewed calibration evidence.
- A FastAPI service, SQLAlchemy repository, PostgreSQL deployment target, local
  SQLite demo, and separate model worker support durable batch processing.
- React, TypeScript, Vite, and Recharts provide the browser application.
- Optional Groq, Gemini, or local Ollama assistance runs only after a user request.
  Saved suggestions and explicit reviewer decisions are persisted separately;
  they do not apply ontology mappings or alter saved predictions and totals.
- Full-review annotations support missing spans, boundary edits, explicit empty
  reviews, status filters, revision conflicts, and provenance-preserving exports.

See [architecture](architecture.md), [LLM assistance boundaries](llm-assistance.md),
and [normalization](normalization.md) for details.

## Interview and viva prompts

**Why use two models?** One predicts aspect spans; the other predicts sentiment
conditioned on an aspect. They solve different tasks and have separate evaluation
evidence.

**What does 0.749563 Macro F1 mean?** It is the equal-class average F1 for
sentiment on gold aspect–sentiment pairs. It says nothing by itself about end-to-end
tag correctness after extraction and normalization.

**Why preserve source offsets?** They let the UI reconnect a predicted phrase and
sentiment context to the exact original review, including long or mixed text.

**Why count one vote per review and aspect?** Repeating a feature word in one
review should not count as multiple independent reviewers supporting a tag.

**What does the robustness panel prove?** It measures sensitivity of the current
saved predictions to removing one review vote. It does not measure correctness,
reviewer independence, or resistance to coordinated manipulation.

**Why use versioned snapshots?** They keep displayed evidence and aggregates tied
to a consistent published data revision while background processing continues.

**What remains unproven?** Representative human-reviewed normalization and
end-to-end tag accuracy, calibrated confidence, domain transfer, public production
readiness, and behavior under concurrent production workloads.

## Evidence to link in a portfolio

- [Measured performance and portfolio-safe metric wording](performance.md)
- [ML implementation and limitations](ml-explained.md)
- [Recorded evaluation and reproduction commands](evaluation.md)
- [Evidence robustness method](evidence-robustness.md)
- [Review quality queue](review-quality.md)
- [Reviewer corrections](review-corrections.md) and [full-review annotations](review-annotations.md)
- [Product comparison limits](product-comparison.md)
- [Faculty demo walkthrough and code pointers](faculty-demo.md)
- [Current release and verification status](release-status.md)
