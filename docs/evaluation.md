# M04 evaluation: saved DistilBERT checkpoints

The current checkpoint and processed data reproduce the Kaggle measurements under the original protocol. The product inference policy is **`full_review`**, selected on validation before the held-out test run and used as the default by the analyzer and transformer wrapper. This applies to gold aspect–sentiment pairs; it is not an end-to-end tag-quality estimate on arbitrary product reviews.

## Inputs and verification

- Notebook: `distilbert_review_generator.ipynb`, training/evaluation cells 9 and 11.
- Data: ignored `data/processed/distilbert/{train,validation,test}.jsonl`.
- Checkpoints: Git LFS-versioned `models/aspect_extractor/distilbert_weighted_lr3e5/best` and `models/sentiment_classifier/distilbert/best`; verified against original Kaggle directory hashes before inference.
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

`full_review` is a dataset-level policy choice, not a guarantee of aspect-local
polarity on contrastive sentences. For example, the same whole-review context
can cause sentiment around “Amazing display but terrible battery” to reflect
the dominant review sentiment instead of the display clause. `local_clause`
remains available for contrast-sensitive use, but did not meet the frozen
validation recall gate and is not the default.

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

The processed validation annotations do not support a complete canonical-tag
score: only 77 of 309 `normalized_aspect` values map through the current
electronics ontology. The remainder include product/device terms and aspect
labels outside this ontology. Scoring only the mapped subset would select an
unrepresentative slice, so the tracked evidence retains separate extraction and
gold-pair sentiment results and leaves end-to-end tag quality unclaimed.

## Commands

From the repository root, with the local `.venv` and Git LFS checkpoints and ignored processed data:

```bash
.venv/bin/python -m pytest tests/unit/test_metrics.py -q
.venv/bin/python scripts/evaluate_pipeline.py validation
.venv/bin/python scripts/evaluate_pipeline.py repeat-validation
.venv/bin/python scripts/evaluate_pipeline.py test
```

The first three commands use validation only. The `test` command requires the frozen policy and rejects an existing test report to prevent accidental repeat or tuning. For this run, validation and test returned exit code 0. The test report records `PASS` for the stated M04 gates; it does not certify deployment behavior or unrelated pipeline components.

After the one-time test report exists, `export-errors` can reproduce the frozen
policy predictions and write every extraction and sentiment error to a separate
directory without changing `validation.json`, `policy.json`, or `test.json`:

```bash
.venv/bin/python scripts/evaluate_pipeline.py export-errors
```

It verifies the validation hash and selected policy first. The two JSONL exports
contain review IDs, spans, labels and probabilities, but omit review text. The
export directory is write-once; choose `--error-export-dir` for another path.

## Additional annotation work

The [external workset](annotation-workset.md) and [browser annotation workspace](review-annotations.md)
support future review and evaluation. Automated proposals remain pending human
review; these tools do not create a new accuracy score or modify this frozen test.
