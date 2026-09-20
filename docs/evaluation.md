# M04 evaluation: saved DistilBERT checkpoints

The current checkpoint and processed data reproduce the Kaggle measurements under the original protocol. The product inference policy is **`full_review`**, selected on validation before the held-out test run. This applies to gold aspect–sentiment pairs; it is not an end-to-end tag-quality estimate on arbitrary product reviews.

## Inputs and verification

- Notebook: `distilbert_review_generator.ipynb`, training/evaluation cells 9 and 11.
- Data: ignored `data/processed/distilbert/{train,validation,test}.jsonl`.
- Checkpoints: ignored `models/aspect_extractor/distilbert_weighted_lr3e5/best` and `models/sentiment_classifier/distilbert/best`; verified against original Kaggle directory hashes before inference.
- Split counts: train 5,936 reviews / 5,107 deduplicated sentiment pairs; validation 326 / 309; test 1,616 / 1,445.
- [Split hash evidence](../audit/evidence/current/split_hashes.json) records both raw JSONL file SHA-256 and the notebook's SHA-256 of UTF-8 `json.dumps(..., sort_keys=True)` for its serialized review lists and deduplicated sentiment-pair lists. All six representation hashes match the unchanged A2/A3 manifests. A raw file hash is not interchangeable with a representation hash.

## Protocol and frozen choice

The notebook's A3 protocol tokenizes `(full review text, gold aspect text)` with `truncation='only_first'` and `max_length=256`, then classifies with label IDs `0=negative`, `1=neutral`, `2=positive`. The current `full_review` path includes M03 aspect-preserving cropping if a review exceeds the model budget. On this data its test predictions have the same confusion matrix as the notebook path. `local_clause` uses the aspect's source offsets to select a nearby clause. These are distinct protocols even when their predictions happen to agree.

Validation comparison on 309 gold pairs:

| Policy | Macro F1 | Negative recall | Neutral recall | Positive recall | Eligible? |
|---|---:|---:|---:|---:|---|
| `full_review` | 0.782950 | 0.843 | 0.571 | 0.919 | Yes |
| `local_clause` | 0.726950 | 0.873 | 0.381 | 0.914 | No |

The predeclared rule chooses the highest Macro F1 among policies with every class recall at least 0.50; a difference within 0.001 favors `full_review`. The [validation report](../audit/evidence/current/validation.json) and [frozen policy](../audit/evidence/current/policy.json) were written before the test command ran. The policy record pins the validation report hash and inference settings.

## Held-out test, run once after the freeze

| Measurement | Current result | Historical reference | Comparison |
|---|---:|---:|---|
| A2 exact-span F1, 1,616 reviews | 0.706179 | 0.706179 | Exact match |
| A2 exact-span precision / recall | 0.648523 / 0.775087 | 0.648523 / 0.775087 | Exact match |
| A3 Macro F1, 1,445 gold pairs | 0.749563 | 0.749563 | Exact match |
| A3 accuracy | 0.824913 | 0.824913 | Exact match |
| A3 negative / neutral / positive recall | 0.837709 / 0.516279 / 0.900123 | Same | Exact match |

The [test report](../audit/evidence/current/test.json) includes exact-span TP=1,120, FP=607, FN=325; the A3 matrix, macro precision/recall, per-class values, error category counts and all gates. The original A2 export contains 597 review-level error entries, and the current count is also 597. Original evidence under `audit/evidence/A2` and `A3` was not changed.

The Kaggle gate reports an A2 rule-baseline F1 of 0.367193 and A3 TF-IDF baseline Macro F1 of 0.617379. Current results exceed both **reported** baselines on matched splits. Baseline artifacts/model weights were not transferred, and this task did not fit or retrain a baseline; independent baseline reproduction is therefore unverified.

The original `A3/sentiment_confusion_matrix.json` says `positive, neutral, negative`, but notebook code constructs rows and columns with numeric IDs `[0,1,2]`, and its per-class recalls confirm the true order is `negative, neutral, positive`. [Corrected derivative](../audit/evidence/current/historical_a3_confusion_corrected.json) records the source file hash and correct row/column semantics. The original remains untouched.

No review text or identifiable error examples appear in the new tracked evidence. Error categories and counts are aggregate only. This evaluation uses gold aspects for A3 and should not be presented as end-to-end performance after extraction, normalization and tag generation.

## Commands

From the repository root, with the local `.venv` and downloaded ignored checkpoints/data:

```bash
.venv/bin/python -m pytest tests/unit/test_metrics.py -q
.venv/bin/python scripts/evaluate_pipeline.py validation
.venv/bin/python scripts/evaluate_pipeline.py repeat-validation
.venv/bin/python scripts/evaluate_pipeline.py test
```

The first three commands use validation only. The `test` command requires the frozen policy and rejects an existing test report to prevent accidental repeat or tuning. For this run, validation and test returned exit code 0. The test report records `PASS` for the stated M04 gates; it does not certify deployment behavior or unrelated pipeline components.
