# Getting started

[Documentation index](README.md) · [Current API](api.md) · [Verification](verification.md)

## Requirements and installation

Use Python **3.11** (the package requires 3.11.x), Node.js **22** (the CI version),
npm, and Git LFS. The trained checkpoints require approximately 508 MB. Training
datasets are not needed for inference.

```bash
git lfs install
git clone https://github.com/sudo8phoenix/Review_tag_generator.git
cd Review_tag_generator
git lfs pull
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[model,backend,test]'
PYTHONPATH=src .venv/bin/python scripts/verify_artifacts.py
npm --prefix frontend ci
```

Checkpoint directories include tokenizer files, configurations, verification
manifests, and Git LFS weights. Preserve their contents so recorded hashes match.
Do not replace unavailable checkpoints with untrained base weights.

## Run locally

```bash
./scripts/start_demo.sh
```

| Service | Default address |
|---|---|
| Browser application | `http://127.0.0.1:5173` |
| API and health | `http://127.0.0.1:8000/api/health` |
| Worker readiness | `http://127.0.0.1:8000/api/ready` |
| Interactive API documentation | `http://127.0.0.1:8000/docs` |

The script runs the API and an embedded inference worker, then starts Vite. It
loads `.env.llm` when present. Stop the launcher with Ctrl+C. SQLite data persists
in `.demo/application.sqlite3`; database backups and exports are local artifacts.

The first startup seeds **Demo laptop** once. If that product was intentionally
deleted earlier, create another product; restarting does not resurrect it.

### Alternate API port

If another application uses port 8000, leave it running and use port 8011. Start
the API from the repository root in one terminal:

```bash
set -a
if [ -f .env.llm ]; then . ./.env.llm; fi
set +a
PYTHONPATH=src .venv/bin/python -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8011
```

Start the frontend in a second terminal:

```bash
API_PROXY_TARGET=http://127.0.0.1:8011 \
  npm --prefix frontend run dev -- --port 5173 --strictPort
```

The browser address stays `http://127.0.0.1:5173`; API documentation is now
`http://127.0.0.1:8011/docs`. The proxy target changes the backend address, not
the `/api/...` routes. Do not start both the default launcher and the manual
frontend on the same port.

### Explicit heuristic demo

```bash
DEMO_MODEL_BACKEND=heuristic ./scripts/start_demo.sh
```

This deliberately selects the rules-based backend with `local_clause` context.
The UI labels it. Trained inference uses `full_review` and does not silently fall
back. Python/backend dependencies and frontend dependencies are still required.

## First workflow

1. Select or create a product.
2. Open **Analyze a review**, enter text, and choose **Preview analysis**.
3. Inspect highlighted aspects and their evidence. Preview does not change totals.
4. Choose **Save review** and wait for the durable job to finish.
5. Open product insights to see published evidence, tags, and review tools.
6. Click a saved aspect to [record a correction](review-corrections.md), or use
   the [annotation workspace](review-annotations.md) to review a full text,
   add missed aspects, adjust boundaries, and track completion.

Product tags require three distinct supporting reviews. A single saved review
can produce mention-level results without establishing a supported product tag.
Corrections and annotations are recorded separately and do not change totals.

## Import files

Imports accept TXT, CSV, JSON, JSONL, and NDJSON, up to 10 MiB and 5,000 rows.
CSV/JSON fields may use `review_text`, `text`, or `reviewText`. TXT uses one review
per nonblank line. Validation reports row errors before processing; preview shows
at most 100 accepted rows, while saving submits the full validated import.

Review duplicate detection is product-scoped. Original text is preserved for
inference; case/whitespace normalization applies only to the duplicate key.
Published evidence and totals remain tied to the last complete snapshot while
new rows process. See [saved-data behavior](saved-data.md) before removing batches.

## Optional LLM setup

Configure Groq, Gemini, or local Ollama using the
[LLM assistance guide](llm-assistance.md). Cloud calls occur only after a user
requests assistance. Keep credentials in ignored server configuration. Manual
review corrections and full-review annotations work without an LLM provider.

## Compose deployment

The deployment recipe uses PostgreSQL, a one-time migration service, API, one
inference worker, and the built frontend. From an installed clone with LFS weights:

```bash
cp .env.release.example .env.release
# Set POSTGRES_PASSWORD in .env.release to a strong generated password.
docker compose --env-file .env.release up --build -d
docker compose --env-file .env.release ps
```

Generate a password with `openssl rand -hex 32`. Open `http://127.0.0.1:8080`;
health is `http://127.0.0.1:8080/api/health`. Startup runs `alembic upgrade head`
through **0005_review_annotations** before starting API and worker. The worker
loads the model bundle; the API uses `RUN_EMBEDDED_WORKER=0`.

Stop services without deleting stored data:

```bash
docker compose --env-file .env.release down
```

PostgreSQL persists in `postgres_data`. Adding `-v` deletes that volume. The public
port binds to localhost; the application has no authentication/tenant boundary.
Add an authenticated deployment boundary before internet exposure.

This recipe is not proof of a completed container deployment. The dependency
lock records macOS ARM64 resolution, and Linux installation, live PostgreSQL,
and clean container startup remain open local verification gates. See
[release status](release-status.md) before describing deployment readiness.

## Troubleshooting

| Symptom | Check |
|---|---|
| Checkpoint missing/hash mismatch | Run `git lfs pull`, retain complete directories, then verify artifacts |
| Port 8000 occupied | Use the alternate-port instructions above |
| Frontend receives 404 for a known API route | Check `API_PROXY_TARGET` and confirm the responding process is this app |
| Jobs stay queued | Check `/api/ready` and the compatible worker heartbeat |
| New annotation endpoints return 404 | Restart the API after updating the checkout; Vite alone reloads only frontend code |
| SQLite schema has not added new tables | Restart the current API; local startup creates additional tables |
| PostgreSQL schema is behind | Run `alembic -c backend/alembic.ini upgrade head` with the intended `DATABASE_URL` configuration |
| Suggest mapping/Ask is disabled | Configure a provider; manual annotations remain available |
| Review save returns 409 | Reload current snapshot/history and reconcile the preserved draft |
| No supported product tags | Check the minimum review support and unknown mappings |

Use the [runtime API reference](api.md) for current endpoints. The
[API v1 design contract](contracts/api-v1.md) is a separate target document.
