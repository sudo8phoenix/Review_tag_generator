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

The quality gate remains pending until that human review is recorded. Unknown
aspects stay visible at mention level but have no canonical product tag.
