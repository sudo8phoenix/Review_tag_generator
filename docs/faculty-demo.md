# Project contributions and faculty demonstration

The project now has three connected tools for examining model-generated review
insights. They are engineering and analysis contributions built around the saved
models; they do not claim that DistilBERT or sensitivity analysis was invented here.

## What to demonstrate

| Feature | Question it answers | Implementation contribution |
|---|---|---|
| Evidence robustness | Would this tag survive losing one review? | Count-weighted single-vote removal, shared classification policy, snapshot provenance and interactive outcomes |
| Review quality queue | Which predictions should a human inspect first? | Deterministic prioritization of unknown aspects, low scores, absent aspects and contradictory sentiment; exportable source evidence |
| Product comparison | How does feature feedback differ between two products? | Canonical-aspect alignment, support checks, model-version compatibility checks and explicit evidence gaps |

All three appear on the product insights page. Robustness and quality reports can
be downloaded as JSON. A download records evidence for discussion; it does not
create human-reviewed labels or retrain the model.

## A repeatable five-minute demonstration

1. Start with `./scripts/start_demo.sh`. For a quick rules-based demonstration use
   `DEMO_MODEL_BACKEND=heuristic ./scripts/start_demo.sh`; the UI labels the backend.
   Use the trained backend when discussing actual ML predictions.
2. Create two products. For a transparent UI demonstration, import these synthetic
   lines into the first product as a TXT file:

   ```text
   Great display.
   Excellent display.
   Amazing display.
   Poor display.
   Terrible display.
   Nothing to report.
   ```

   Import `Poor display.`, `Terrible display.`, and `Bad display.` as separate lines
   for the second product. Wait for both imports to complete.
3. Open the first product's insights. With the heuristic backend these examples
   give three positive and two negative display votes. In Evidence robustness,
   remove one positive vote. The classification changes from good to weak. Only
   removing one of the two negative votes preserves the positive tag, giving 40%
   tag stability. This shows that a published tag can be sensitive despite meeting
   the minimum support threshold.
4. Inspect Review quality queue. “Nothing to report.” has no detected aspect in
   the heuristic demonstration and is suggested for inspection. Export the JSON
   and show the original text, reasons, offsets and saved model evidence.
5. In Compare observed feedback, select the second product and compare. Explain
   that the displayed balance compares predicted feature feedback and depends on
   sample composition. A product with fewer than three supporting aspect reviews
   has an evidence gap, and different pipeline versions suppress direction.
6. Click a highlighted aspect in Review evidence to connect a prediction to the
   exact source phrase and sentiment context. Use [the ML guide](ml-explained.md)
   to explain the extraction and sentiment models separately.

Synthetic demonstration examples are not evaluation data and must not be used to
claim accuracy. Trained predictions may differ from the heuristic outputs above.

## How to explain the work

A defensible project description is: “We implemented an aspect-based review
analysis system using two fine-tuned DistilBERT models, then built an evidence
layer that preserves source spans, aggregates one vote per review and aspect,
checks tag sensitivity, prioritizes predictions for review, and compares product
feedback only when support and model-version requirements are met.”

Be prepared to explain these design choices:

- **Two models:** extraction finds spans; aspect-conditioned sentiment labels
  those spans. Sentiment on gold aspects is a different evaluation from end-to-end tags.
- **One vote per review-aspect:** repeated wording must not inflate support.
- **Published snapshots:** an unfinished import must not mix new evidence with old totals.
- **Tag versus classification stability:** good and excellent use the same positive
  tag family, so a classification can change without changing the tag.
- **Human review suggestions:** confidence is uncalibrated and a flag is not proof
  of an error. Human-approved corrections and automatic retraining are future work.
- **Comparison limits:** sampling differences and model errors can explain an
  observed gap; it is not proof that one product is objectively better.

## Files to show during code review

- `src/review_tag_generator/evidence_audit.py`: analytic leave-one-review-out report.
- `src/review_tag_generator/quality_queue.py`: human review prioritization.
- `src/review_tag_generator/comparison.py`: support-aware comparison.
- `frontend/src/components/`: the three corresponding interactive panels.
- `tests/unit/`, `tests/integration/test_application.py`, and
  `frontend/e2e/evidence-tools.spec.ts`: pure, HTTP/storage and browser verification.

## GitHub CI collection fix

The non-model CI job intentionally installs backend/test dependencies without
PyTorch. Pytest imports modules during collection before excluding marked tests.
A top-level `import torch` in `tests/model/test_long_reviews.py` therefore failed
before `-m 'not model'` could deselect that file's model tests. Moving that import
inside the model test preserves real-model coverage and keeps collection independent
of optional inference dependencies. Locally, the non-model suite was also exercised
with import hooks that explicitly block both `torch` and `transformers`.

Live PostgreSQL and remote GitHub CI results require their own execution evidence;
a local collection fix is not a claim that every remote release check has passed.


## Optional LLM demonstration

With a server-side key configured, open an unknown aspect and request a suggested
mapping. Explain why an ontology mapping can be missing even when extraction and
sentiment confidence are high. Show that a new feature proposal is distinct from
an accepted canonical mapping and does not silently change product totals.

On the product page, ask a specific question about an observed feature and inspect
the cited quotes. This combines retrieval, structured generation, source validation,
and snapshot provenance. It does not establish that an LLM answer is always correct.
See [LLM setup and verification limits](llm-assistance.md).
