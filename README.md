# Review Tag Generator

The service extracts aspects, predicts their sentiment, normalizes aliases,
generates customer-facing tags, and aggregates product insights. The deployed
API uses the verified DistilBERT checkpoints and evaluates sentiment with the
full review as context (`full_review`). It does not silently switch models when
checkpoints or inference dependencies are unavailable.

See [release status and remaining evidence gates](docs/release-status.md).
For a complete explanation of the models, training, inference, and measured
limitations, read [the ML guide](docs/ml-explained.md).

## Optional LLM assistance

Unknown aspect evidence drawers now offer **Suggest mapping**, and product pages
include **Ask about these reviews** with source citations. Groq, Gemini, and local
Ollama are supported. Calls run only on request; suggestions do not overwrite the
trained pipeline or product totals. See [setup, usage, and validation](docs/llm-assistance.md).

## Project demonstration tools

The product insights page now includes an interactive robustness audit, a
[review quality queue](docs/review-quality.md) with prediction-evidence export,
and [product comparison](docs/product-comparison.md) with support and model-version
checks. These operate on saved review predictions and published snapshots.

See [the faculty demo and contribution guide](docs/faculty-demo.md) for examples,
code pointers, and a clear explanation of the project's contributions.

## Evidence robustness audit

The project now checks whether product tags survive removing a single supporting
review. The report distinguishes disagreements between reviewers from contradictory
mentions inside one review, and explains which vote removals would change a tag.
It runs on the published snapshot without additional inference.

```bash
curl --fail http://127.0.0.1:8000/api/demo/products/demo-laptop/evidence-audit
```

See [the method, examples, and limitations](docs/evidence-robustness.md). This is
an implemented sensitivity feature, not a claim of a new model architecture.

Run the demo from the project root:

```bash
python3 scripts/run_demo.py
```

Use the library with `PYTHONPATH=src`. The main entry point is `ReviewAnalyzer`; its `analyze(review)` method returns mention-level tags and `aggregate(reviews)` returns product strengths, weaknesses, sentiment counts, aspect frequencies, and representative reviews.

The winning DistilBERT checkpoints, evaluation results, and dataset hashes are
recorded in [audit/evidence](audit/evidence). The heuristic analyzer is a
separate explicit mode for local demonstrations: run
`DEMO_MODEL_BACKEND=heuristic ./scripts/start_demo.sh`. It uses
`local_clause` sentiment context and is labeled in the UI; the deployed
transformer service remains on `full_review`. The standalone Python library
`ReviewAnalyzer(use_transformer="auto")` currently requires trained artifacts
and behaves like `True`; use `False` to select the heuristic path explicitly.

Core assertions can be run without model dependencies using the explicit heuristic:

```bash
PYTHONPATH=src python3 - <<'PY'
from review_tag_generator import Review, ReviewAnalyzer
result = ReviewAnalyzer(use_transformer=False).analyze(Review("r1", "p1", "Amazing display but terrible battery."))
print(result["tags"])
PY
```

## Compose deployment

The Compose stack runs PostgreSQL, the API, one inference worker, and the built
web UI. The API and worker share the same image and verified DistilBERT model
checkpoints. PostgreSQL data lives in the `postgres_data` Docker volume, so it
survives container replacement. The UI is available at http://127.0.0.1:8080.

Install Git LFS and pull the model artifacts before building. Then create a
release environment file and start the stack:

```bash
git lfs install
git lfs pull
cp .env.release.example .env.release
# Replace POSTGRES_PASSWORD in .env.release with `openssl rand -hex 32` output.
docker compose --env-file .env.release up --build -d
```

Compose waits for PostgreSQL health, runs `alembic upgrade head`, and then
starts the API and worker. Check service state with
`docker compose --env-file .env.release ps` and API health at
http://127.0.0.1:8080/api/health. Stop the services with
`docker compose --env-file .env.release down`; add `-v` only when you intend to
delete the database volume.

The published UI port binds to localhost. The API has no authentication yet,
so keep the stack behind a trusted local network or add an authenticated
reverse proxy before exposing it to the internet. The model checkpoints add
about 508 MB to the image. Python dependencies are installed from the pinned
`requirements.lock` and `requirements-inference.txt` files. The checked-in lock
records a macOS ARM64 resolution; the Linux container dependency set has not
been resolved or verified on this host.

## Faculty demo

With the local `.venv` and frontend dependencies installed, start both services:

```bash
./scripts/start_demo.sh
```

Open http://127.0.0.1:5173. Select **Demo laptop**, preview a review, then
choose **Save review**. Preview leaves product totals unchanged; saving creates
a durable analysis job. The local default uses SQLite at
`.demo/application.sqlite3`; the Compose stack uses PostgreSQL. Product
snapshots update when the worker finishes each job. While processing continues,
review evidence, totals, and revision remain tied to the last published snapshot.
Live previews run between bulk rows so imports do not block the whole preview
queue. With `RUN_EMBEDDED_WORKER=0`, the API reads runtime metadata without
loading the inference models; the separate worker owns the model bundle. Aggregate tags need
three supporting reviews. Imports accept `.txt`, `.csv`, `.json`, `.jsonl`, and
`.ndjson` files (up to 10 MiB and 5,000 rows). CSV headers and JSON objects may
use `review_text`, `text`, or `reviewText`; invalid rows are reported with
their row number. The UI calls `POST /api/demo/imports/validate` before
previewing an import. It previews at most 100 accepted rows, then submits the
full file for processing.

The live API uses `/api/health` and `/api/demo/...` routes. Review preview is
`POST /api/demo/products/{id}/preview` with `{"reviews":["..."]}`; it returns
queued preview IDs (no immediate analysis). Poll each ID at
`/api/demo/previews/{id}` until it reaches `completed` or `failed`. Previews
expire after 30 minutes and do not update product totals.
Saving reviews uses `POST /api/demo/products/{id}/reviews` (or `/jobs`) with the
same body and returns a `202` job. Imports use
`POST /api/demo/products/{id}/imports` with JSON `filename` and `content`.
Use `POST /api/demo/imports/validate` with the same body to validate a file
without saving it. Poll `/api/demo/jobs/{id}` for job progress and read the current product
snapshot from `/api/demo/products/{id}`. The frontend and OpenAPI page are at
http://127.0.0.1:5173 and http://127.0.0.1:8000/docs.
`GET /api/models/metrics` reports saved evaluation evidence and currently marks
the human normalization gate as pending.

The routes and payloads in [the API v1 contract](docs/contracts/api-v1.md) are
the target contract; its versioned `/api/...` route table is not the live
router. [The aggregation contract](docs/contracts/aggregation.md) records the
aggregation policy and core function behavior. The live service has no
authentication and should remain bound to localhost. Checkpoints are included
through Git LFS. If checkpoints are unavailable, explicitly run
`DEMO_MODEL_BACKEND=heuristic ./scripts/start_demo.sh`; the UI labels this mode.

## Install from a fresh clone

Install Git LFS before cloning. The two trained checkpoints require approximately
508 MB of downloads; raw training datasets are not required for inference.

```bash
git lfs install
git clone https://github.com/sudo8phoenix/Review_tag_generator.git
cd Review_tag_generator
git lfs pull
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[model,backend,test]'
PYTHONPATH=src .venv/bin/python scripts/verify_artifacts.py
npm --prefix frontend ci
./scripts/start_demo.sh
```

The tokenizer files, model configurations, verification manifests, ontology,
and dependency files are included in Git. Keep the complete checkpoint
directories intact so their hashes match the recorded training manifests.
