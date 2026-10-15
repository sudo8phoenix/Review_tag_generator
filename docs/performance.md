# Performance and evidence

There are three different measurements to discuss in a portfolio: prediction
quality, application responsiveness, and engineering verification. They answer
different questions and should not be merged into one “accuracy” number.

## Held-out ML quality

| Task and protocol | Measured value | Evidence |
|---|---:|---|
| Aspect extraction, exact-span F1 | **70.62%** | [Frozen test report](../audit/evidence/current/test.json) |
| Aspect extraction precision | 64.85% | Same frozen test report |
| Aspect extraction recall | 77.51% | Same frozen test report |
| Aspect-conditioned sentiment Macro F1, gold aspects | **74.96%** | Same frozen test report |
| Aspect-conditioned sentiment accuracy, gold aspects | **82.49%** | Same frozen test report |
| Negative / neutral / positive recall | 83.77% / 51.63% / 90.01% | Same frozen test report |

The test contains 1,616 extraction reviews and 1,445 gold sentiment pairs. The
sentiment policy was selected on validation before evaluating the frozen test:
`full_review` met the per-class recall gate, while `local_clause` did not.
See [methodology](evaluation.md) for the exact values, split hashes, and caveats.

The historical run reports a rule-baseline extraction F1 of 36.72% and TF-IDF
sentiment Macro F1 of 61.74%. The recorded trained results are 33.90 and 13.22
percentage points higher, respectively, on the documented matched splits. These
baselines were not independently rerun locally because their original fitted
artifacts were not transferred. Describe the comparison as a reported baseline
comparison, not a newly reproduced experiment.

There is no approved human-reviewed normalization or end-to-end canonical-tag
accuracy score. LLM assistance has live connectivity/grounding smoke checks, not a
representative accuracy evaluation. Do not multiply the component scores or present
82.49% as the accuracy of generated product tags.

## Local live-preview timing

A small smoke measurement was performed on 2026-10-15 with the trained transformer
backend, `full_review` context, local SQLite, Python 3.11.15, and an Apple M4 ARM64
machine. Models were already loaded. One warm-up request was excluded, followed
by ten sequential short synthetic review previews with no competing workload.

| Enqueue-to-completed preview metric | Measured time |
|---|---:|
| Median | **566.45 ms** |
| Mean | 562.57 ms |
| Minimum / maximum | 515.46 / 599.49 ms |
| Nearest-rank sample p95 | 599.49 ms |

These times include the HTTP enqueue, worker scheduling/queue delay, extraction,
sentiment, normalization, and polling at 50 ms intervals. The worker can sleep
for 500 ms between idle checks, so these are application completion times, not
model-only inference speed. Browser polling defaults can also change perceived
latency. The small sample p95 equals the maximum by the nearest-rank definition;
it is not a production tail-latency guarantee.

The run used 24–49 character synthetic reviews and one client. It did not measure
cold model startup, maximum-length reviews, concurrent throughput, large imports,
PostgreSQL deployment, cloud LLM latency, memory usage, or public-network traffic.
Do not generalize this smoke result into an SLA or “thousands of reviews per second”.

Raw timings, host context, pipeline version and a source-tree hash are recorded in
[the latency artifact](../audit/evidence/current/preview-latency.json). No real
customer review text or credentials are included. The script removes its temporary
product and previews after successful completion.

Reproduce against a local running API with removal controls available:

```bash
.venv/bin/python scripts/benchmark_preview.py \
  --base-url http://127.0.0.1:8011 \
  --samples 10 \
  --output /tmp/review-tag-preview-latency.json
```

Keep the output separate from the frozen artifact unless intentionally recording
a new run. If a preview fails or remains active, inspect its temporary product
before manually removing it; the script reports cleanup failure rather than
claiming that it removed active work.

## Engineering verification

The latest full Python run passed **262 tests** with **2 PostgreSQL checks skipped**.
The browser suite covers navigation, review preview/save, recovery, robustness,
comparison, LLM UI with injected provider responses, import removal, clearing,
product deletion, and draft cleanup. Current counts are recorded in
[release status](release-status.md). Frontend lint, TypeScript/production build,
and unit checks pass.

The deletion checks assert transactional cleanup, other-product isolation,
per-import review ownership, shared regeneration references, duplicate-only batches,
active-work rejection, and no automatic resurrection of a deleted demo product.
PostgreSQL migration SQL was generated successfully through migration 0003; live
PostgreSQL execution is still a separate requirement. Local tests are not proof
that the latest remote GitHub Actions or container release checks are green.

## Safe portfolio wording

> Evaluated a two-stage aspect-based sentiment pipeline with 70.62% exact-span
> extraction F1 and 74.96% sentiment Macro F1 on gold aspects. Built a traceable
> product workflow with evidence spans, durable processing, tag sensitivity checks,
> and cited LLM assistance. A ten-sample local smoke run measured 566 ms median
> preview completion on an Apple M4; this was not a production load test.

For a short metrics strip, use “70.62% extraction F1”, “74.96% sentiment Macro F1
(gold aspects)”, and “566 ms local median preview (n=10)”. Include the protocol
qualifiers directly beside the numbers, and link the evidence.
