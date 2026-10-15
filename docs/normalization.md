# Aspect normalization evidence

M05 uses `electronics-aspects-v1`, a 21-aspect laptop/electronics ontology.
Normalization is alias-first: case and whitespace variants of explicit aliases
map deterministically, while terms with no owning alias remain unknown. This
prevents an unsupported noun or adjective from becoming a customer-facing tag.

Semantic normalization is deliberately disabled by default. It requires a local
`sentence-transformers/all-MiniLM-L6-v2` snapshot at the pinned revision in
`review_tag_generator.normalization`, an explicit calibrated threshold, and no
network access at inference time. The evaluator searches thresholds from 0.50
through 0.90 in 0.02 increments, choosing highest development accuracy, then
fewer false-known mappings, then the higher threshold.

Run the fixture-only evaluator with:

```bash
.venv/bin/python scripts/evaluate_normalization.py
```

The built-in 100 development and 100 held-out rows are synthetic regression
fixtures. They are not human ground truth and cannot support an accuracy claim.
Before enabling semantic normalization in a release, provide 200 human-reviewed
JSONL rows (100 development then 100 held-out) and a local pinned model snapshot:

```bash
.venv/bin/python scripts/evaluate_normalization.py \
  --model-path /path/to/all-MiniLM-L6-v2 \
  --examples-jsonl /path/to/human-reviewed-normalization.jsonl
```

The evaluator records the input file SHA-256 for supplied rows and keeps the
quality gate at `pending human review` even when the input is labelled human data:
the file alone cannot verify who reviewed it or how disagreements were settled.
Record reviewer and adjudication provenance separately, then have a human owner
review the development and held-out reports before considering semantic mode for
release. Threshold selection uses development rows only (accuracy, then fewer
false-known unknowns, then higher threshold); the held-out split is reported
once at the selected threshold and does not influence calibration. Unknown
aspects stay visible at mention level but have no canonical product tag.

When a raw mention is ambiguous, such as `charge`, semantic matching requires
review context. The query keeps the mention explicit and adds context in a
separate prompt field. Exact ontology aliases continue to resolve first.

`ReviewAnalyzer` remains alias-only by default. A caller can explicitly enable
the local semantic matcher by supplying all three settings:

```python
from review_tag_generator import ReviewAnalyzer
from review_tag_generator.normalization import MINILM_REVISION

def make_analyzer(reviewed_threshold: float) -> ReviewAnalyzer:
    # Supply only after reviewing a human-labelled calibration report.
    return ReviewAnalyzer(
        semantic_model_path="/path/to/all-MiniLM-L6-v2",
        semantic_revision=MINILM_REVISION,
        normalization_threshold=reviewed_threshold,
    )
```

There is no approved calibration artifact in the repository today, so this
setting is not enabled by default. The JSON report's selected threshold is a
candidate from its development rows; the pending quality gate still applies.


For the running API and worker, use the same explicit environment settings:
`SEMANTIC_MODEL_PATH`, `SEMANTIC_MODEL_REVISION`, and
`NORMALIZATION_THRESHOLD`. The model snapshot is loaded locally; the service
never downloads a semantic model implicitly. The running pipeline fingerprint
includes these settings so differently configured workers cannot consume one
another's jobs.

## Relationship to annotation tasks

The [external annotation workset](annotation-workset.md) contains 200 complete
reviews split into development and held-out tasks. It is distinct from a reviewed
normalization calibration set of aspect phrases. Automated draft annotations do
not satisfy the human calibration gate or justify enabling semantic matching.
