# Electronics annotation workset

The initial workset uses **Virtual Assistant Devices Dataset**, version 1,
by Yaser alhasawi and Salem Algamdi, DOI
[10.17632/d5vsgcxrk5.1](https://data.mendeley.com/datasets/d5vsgcxrk5/1).
The publisher lists [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The accompanying research is
[Aspect-based sentiment analysis in smart devices](https://doi.org/10.1016/j.dib.2024.110642).
Retain this attribution when using derived data.

This is a smart assistant device dataset, not a laptop benchmark. It gives us
real electronics examples for assessing domain transfer and unknown aspects.
It does not replace the existing frozen laptop results.

## What was downloaded and checked

The 364,637-byte workbook is saved locally at
`data/raw/virtual_assistant_devices/devices-v1.xlsx`. Its SHA-256 matches the
publisher metadata:
`7625ec57846d671f21de8c4df69c4e348e04864eaac378d8cb2a3353d661480d`.

The workbook contains 2,370 reviews. The actual sentiment distribution is
842 positive, 774 negative, and 754 neutral. The dataset description instead
reports 842/800/728; we retain the workbook labels and record this discrepancy.
Aspect categories span columns G through K, including sparse extra categories.
Device, company and website metadata carry forward across blank cells in the
publisher's grouped layout. Review text is retained exactly as stored in column E.

The labels describe review sentiment and aspect categories. There are no exact
aspect offsets, per-mention polarity labels, or labels for our canonical ontology.
Neither source sentiment nor model predictions are promoted to those missing labels.

There are 2,339 normalized-text groups, including 31 duplicate rows. Comparing
against all three existing DistilBERT splits found one group matching training
text and no matches to validation or test. After excluding overlap, there are
2,338 eligible groups. Comparison uses NFKC, case folding and Unicode word tokens;
it ignores punctuation and whitespace and does not establish semantic independence.
There were no duplicate groups with conflicting source sentiment labels.

## Reproduce preparation

```bash
.venv/bin/python scripts/prepare_review_annotations.py download
.venv/bin/python scripts/prepare_review_annotations.py prepare
```

Preparation requires the existing `data/processed/distilbert/{train,validation,test}.jsonl`
files for the overlap audit. It fails if any are missing. The downloader accepts
only the pinned publisher hash, and preparation refuses to overwrite an existing
workset. Use `prepare --output data/annotations/another-workset` for a new run.

The ignored `data/annotations/virtual-assistant-v1/` directory contains:

- `eligible-reviews.jsonl`: unique eligible source review groups, with provenance.
- `development.jsonl`: 100 pending annotation tasks.
- `heldout.jsonl`: 100 separate pending annotation tasks.
- `manifest.json`: source, license, input/output hashes, overlap audit and limitations.

Each split has 34 source-negative, 33 source-neutral and 33 source-positive reviews.
Selection follows a fixed hash order within each source-sentiment stratum and does
not depend on model outputs. Duplicate groups cannot cross the split boundary.
The sample is deliberately balanced, so its scores will not estimate natural
production prevalence. A text group can occur on multiple devices; its source row
list preserves those references and the earliest row supplies display metadata.

## Development diagnostics

```bash
.venv/bin/python scripts/prepare_review_annotations.py predict-development
```

This runs the verified trained checkpoints with `full_review` and alias-only
normalization, using the default CPU inference configuration. It writes separate
`development-predictions/predictions.jsonl`, `quality-queue.jsonl` and `summary.json`
files without editing annotation tasks. It never predicts the held-out split.
The output directory cannot be overwritten accidentally.

The first development run analyzed 100 reviews and returned 180 mentions. Of those,
156 had no canonical mapping. Twenty reviews had no detected aspects; 96 reviews
entered the quality queue. These are model behavior counts, not correctness
measurements. Some unknowns may be appropriate because the 21-aspect ontology
does not cover all smart-device features. Review those cases before changing
aliases or extending the ontology.

The text-free manifest and diagnostic summary are retained in
`audit/evidence/annotation-bootstrap/`. Review texts and individual predictions
remain under ignored `data/` paths. The recorded run hashes the source tasks,
predictions, core Python source tree and both verified model weight files.

## Record human corrections

An automated draft review of all 100 development tasks is saved locally as
`development-proposed.jsonl`. It contains 204 proposed explicit mentions: 86
mapped to existing canonical IDs and 118 outside the ontology. Twenty-seven
reviews have no proposed explicit aspects. Seventy-four reviews have flags
covering implicit aspects, ambiguous boundaries or sentiment, comparison devices,
missing features, non-product complaints and source artifacts.

These are proposals, not independent human annotations. Every task remains
`pending`, with `review_method: automated` and reviewer provenance recorded in its
annotation object. The original development and held-out tasks remain unchanged.
The draft was based on reading development source text; it does not constitute an
accuracy evaluation or approval of the pipeline. Review flags need adjudication,
and unflagged rows still require checking for missed aspects and incorrect labels.

The exact-phrase decisions are in ignored `review-drafts/decisions.json`, tied to
the original task-file hash. To rebuild into a new output file:

```bash
.venv/bin/python scripts/prepare_review_annotations.py build-review-proposals \
  --decisions data/annotations/virtual-assistant-v1/review-drafts/decisions.json \
  --output data/annotations/virtual-assistant-v1/development-proposed-copy.jsonl
```

The builder validates task coverage, phrase occurrences, spans, ontology IDs,
sentiment and held-out integrity. It refuses to overwrite an existing output.
The validator also checks proposed spans on pending tasks, and rejects automated
proposals marked approved. For an actual human review, copy the proposal file,
check every mention and omission, record the person's reviewer ID and review
date, set `review_method` to `human`, and set `status` to `approved` only after
completing the task. Preserve the original proposals as provenance.

Copy the development task file to a separate working file. Keep the original
review text, split, ID and source metadata unchanged. Edit only `annotation`.
Read the full review and label every explicit aspect mention independently of
the source categories and model suggestions. For example, for the synthetic text
`Bad screen, great wifi.`:

```json
{
  "status": "approved",
  "reviewer": "your-reviewer-id",
  "notes": "Wi-Fi is outside the current ontology.",
  "mentions": [
    {"start_char": 4, "end_char": 10, "raw_aspect": "screen", "canonical_id": "display", "sentiment": "negative"},
    {"start_char": 18, "end_char": 22, "raw_aspect": "wifi", "canonical_id": null, "sentiment": "positive"}
  ]
}
```

Offsets use zero-based Unicode code-point indices, with the end excluded, matching
Python string slices and the core pipeline. Canonical IDs come from
`src/review_tag_generator/data/ontology-v1.json`; use explicit `null` when outside
the ontology. Do not treat an unrecognized synonym as automatically out of scope.
An approved empty mentions list means a person verified that there are no explicit
aspects. Implicit aspects are outside this span-based evaluation. Resolve ambiguous
sentiment or aspect boundaries with a second reviewer before approval, and explain
the decision in notes. Record reviewer identities, review dates and adjudication
method separately. The validator checks structure; it cannot certify human work.

```bash
cp data/annotations/virtual-assistant-v1/development.jsonl \
   data/annotations/virtual-assistant-v1/development-reviewed.jsonl
.venv/bin/python scripts/prepare_review_annotations.py validate-annotations \
  --split development \
  --reviewed data/annotations/virtual-assistant-v1/development-reviewed.jsonl
```

Validation reports pending tasks and rejects unknown IDs, changed source text,
missing reviewer identities on approved rows, invalid offsets, mismatched span
text, invalid sentiment, missing canonical decisions and duplicate spans.

Once all development tasks are approved:

```bash
.venv/bin/python scripts/prepare_review_annotations.py score-development \
  --reviewed data/annotations/virtual-assistant-v1/development-reviewed.jsonl \
  --output-report data/annotations/virtual-assistant-v1/development-score.json
```

Scoring checks the recorded prediction and input hashes, then reports micro
precision/recall/F1 for exact spans and for joint `(span, canonical ID, sentiment)`
tags. Incorrect known mappings for gold unknowns count as false positives. Unknown
mentions still participate in extraction scoring. Undefined rates are `null`.
This evaluates explicit mention-level tags, not product-level aggregate judgments.
The command refuses pending annotations and existing output reports.

Use development errors to plan changes. Annotate held-out tasks independently,
preferably without exposing predictions to their reviewers. Freeze the candidate
pipeline and ontology after development work and record that choice before any
held-out inference. This tool intentionally provides no held-out prediction or
scoring command yet. No new end-to-end accuracy or release approval is claimed.
