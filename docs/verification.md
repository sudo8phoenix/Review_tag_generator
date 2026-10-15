# Verification

[Documentation index](README.md) · [Current results](release-status.md)

Run commands from the repository root after [installation](getting-started.md).
Use disposable databases for verification; browser suites create and remove test
products. Do not point automated mutation tests at saved user data.

## Python

```bash
.venv/bin/python -m pytest -q
```

Model tests require downloaded, verified trained checkpoints and inference
dependencies. To run backend and unit checks without model inference:

```bash
.venv/bin/python -m pytest -m 'not model' -q
```

Focused reviewer workflows:

```bash
.venv/bin/python -m pytest \
  tests/integration/test_corrections.py \
  tests/integration/test_annotations.py \
  tests/unit/test_review_annotations.py -q
```

These checks exercise separate reviewer records, exact source spans, Unicode,
idempotent retries, stale/concurrent writes, progress, annotation exports, and
cascading deletion. They do not establish human annotation quality.

## Frontend

```bash
npm --prefix frontend run lint
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

The unit suite includes conversion from browser selections to source-code-point
offsets, including emoji and CRLF/CR normalization. A Vite chunk-size advisory is
currently emitted by a successful build; it is not a failed type/build check.

## Isolated browser workflows

Install the browser once:

```bash
npm --prefix frontend exec -- playwright install chromium
```

In terminal A, start a separate heuristic test API:

```bash
DEMO_MODEL_BACKEND=heuristic \
DEMO_DATABASE=.demo/verification.sqlite3 \
PYTHONPATH=src .venv/bin/python -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8012
```

In terminal B, use a separate frontend port:

```bash
API_PROXY_TARGET=http://127.0.0.1:8012 PLAYWRIGHT_PORT=5174 \
  npm --prefix frontend run test:e2e
```

Playwright starts Vite on port 5174. If a server already occupies that port, make
sure it points to the isolated API or choose another `PLAYWRIGHT_PORT`; the
configuration can reuse an existing local server. Stop terminal A when done.

For the new workflows only:

```bash
API_PROXY_TARGET=http://127.0.0.1:8012 PLAYWRIGHT_PORT=5174 \
  npm --prefix frontend run test:e2e -- \
  review-corrections.spec.ts review-annotations.spec.ts
```

Tests cover provider-assisted accept/edit/reject using injected responses and
real browser/API/database correction and annotation flows using the heuristic
backend. Provider injection is explicit and does not claim a live LLM call.
Responsive screenshots and traces are kept in ignored `frontend/test-results/`.
Public documentation uses only selected synthetic-data captures with provenance.

## PostgreSQL and migrations

Supply `POSTGRES_TEST_URL` for a disposable PostgreSQL database whose name contains
`test`, using a `postgresql+psycopg://` URL. Migration tests downgrade that database
before upgrading it, so do not supply a database containing data to retain.

```bash
.venv/bin/python -m pytest \
  tests/integration/test_migrations.py \
  tests/integration/test_postgres_repository.py -q
```

The CI workflow provisions its own PostgreSQL test service. Without the variable,
these two suites skip. SQLite does not substitute for PostgreSQL-specific checks.

Generate PostgreSQL upgrade SQL without a running database:

```bash
PYTHONPATH=src .venv/bin/python -m alembic \
  -c backend/alembic.ini upgrade head --sql > /tmp/review-tag-migrations.sql
```

The current head is **0005_review_annotations**. SQL generation verifies a
migration script path; it does not prove that live upgrade/downgrade or Linux
container deployment succeeds. See [release status](release-status.md).

## Dataset and evidence checks

```bash
PYTHONPATH=src .venv/bin/python scripts/verify_artifacts.py
.venv/bin/python scripts/prepare_review_annotations.py --help
```

Use [the workset guide](annotation-workset.md) for download, preparation,
proposals, validation, and development scoring. Source labels and automated
proposals must not be counted as missing human gold annotations.

The frozen model test report is already present. Do not rerun its write-once
`test` command to tune a model or overwrite published evidence. Read
[the evaluation protocol](evaluation.md) before reproducing ML measurements.
