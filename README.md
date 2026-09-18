# Review Tag Generator

The repository now includes a small, deterministic end-to-end core for laptop and consumer-electronics reviews. It extracts known aspects, predicts clause-local aspect sentiment, normalizes aliases, generates customer-facing tags, and aggregates product insights.

Run the demo from the project root:

```bash
python3 scripts/run_demo.py
```

Use the library with `PYTHONPATH=src`. The main entry point is `ReviewAnalyzer`; its `analyze(review)` method returns mention-level tags and `aggregate(reviews)` returns product strengths, weaknesses, sentiment counts, aspect frequencies, and representative reviews.

The deterministic fallback is intended for local pipeline validation. The winning DistilBERT checkpoints, gate results, and dataset hashes are recorded in [audit/evidence/winning-run.json](audit/evidence/winning-run.json). Held-out error samples still need to be exported into the local evidence file.

The trained checkpoints are now present under `models/`. Install the optional inference dependencies with Python 3.10+ and run `ReviewAnalyzer(use_transformer=True)` to force real DistilBERT inference. With `use_transformer="auto"` (the default), the analyzer loads the checkpoints when dependencies are available and otherwise uses the deterministic fallback.

At inference time, sentiment receives the conjunction-separated clause containing the aspect. This prevents a negative opinion about the battery from changing the sentiment of a positively described display in the same review.

Core assertions can be run without third-party packages:

```bash
PYTHONPATH=src python3 - <<'PY'
from review_tag_generator import Review, ReviewAnalyzer
result = ReviewAnalyzer().analyze(Review("r1", "p1", "Amazing display but terrible battery."))
print(result["tags"])
PY
```
