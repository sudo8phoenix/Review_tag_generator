from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.migrate_legacy_demo import export_legacy_reviews
from scripts.import_amazon import ImportErrorDetail, run_import


def write_source(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_lost_post_response_resumes_same_batch_key_and_content(tmp_path):
    source = tmp_path / "amazon.jsonl"
    write_source(source, [{"review_id": "r1", "parent_asin": "A1", "text": "Review one."}])
    state = tmp_path / "state.json"
    first_attempt = []

    def lost_response(url, *, method="GET", body=None, idempotency_key=None):
        first_attempt.append((url, method, body, idempotency_key))
        raise OSError("connection dropped after server accepted request")

    with pytest.raises(OSError):
        run_import(source=source, product_id="product-1", base_url="http://server",
                   state_path=state, poll_interval=0, request_json=lost_response)

    saved_pending = json.loads(state.read_text())["pending"]
    second_attempt = []

    def recovered(url, *, method="GET", body=None, idempotency_key=None):
        second_attempt.append((url, method, body, idempotency_key))
        if method == "POST":
            return {"id": "job-1"}
        return {"id": "job-1", "status": "completed", "completed_rows": 1,
                "errors": [], "failed_rows": 0, "rejected_rows": 0}

    assert run_import(source=source, product_id="product-1", base_url="http://server",
                      state_path=state, poll_interval=0, request_json=recovered) == 0
    post = second_attempt[0]
    assert post[1] == "POST"
    assert post[2]["content"] == saved_pending["content"]
    assert post[3] == saved_pending["idempotency_key"]
    assert len(first_attempt) == 1
    assert json.loads(state.read_text())["complete"] is True


def test_changed_source_refuses_resume(tmp_path):
    source = tmp_path / "amazon.jsonl"
    write_source(source, [{"text": "Original."}])
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"version": 1, "source": str(source.resolve()),
        "source_sha256": "wrong", "product_id": "product-1", "asins": [],
        "base_url": "http://server", "cursor": 0, "source_line": 0,
        "next_batch": 1, "pending": None, "complete": False}))
    with pytest.raises(ImportErrorDetail, match="source_sha256"):
        run_import(source=source, product_id="product-1", base_url="http://server",
                   state_path=state, request_json=lambda *args, **kwargs: pytest.fail("HTTP must not run"))


def test_row_errors_export_and_block_later_batches_until_explicit_skip(tmp_path):
    source = tmp_path / "amazon.jsonl"
    write_source(source, [{"text": "First."}, {"text": "Second."}])
    state = tmp_path / "state.json"
    calls = []

    def failed_first_batch(url, *, method="GET", body=None, idempotency_key=None):
        calls.append(method)
        if method == "POST":
            return {"id": "job-error"}
        return {"id": "job-error", "status": "completed_with_errors", "completed_rows": 0,
                "errors": [{"row": "1", "error": "invalid review", "status": "rejected"}],
                "failed_rows": 0, "rejected_rows": 1}

    assert run_import(source=source, product_id="product-1", base_url="http://server",
                      state_path=state, batch_size=1, poll_interval=0,
                      request_json=failed_first_batch) == 2
    state_after_error = json.loads(state.read_text())
    pending = state_after_error["pending"]
    exported = Path(pending["error_export"])
    assert json.loads(exported.read_text()) == {
        "batch_row": 1, "error": "invalid review", "source_line": 1, "status": "rejected"}
    assert state_after_error["cursor"] == 0

    def successful(url, *, method="GET", body=None, idempotency_key=None):
        if method == "POST":
            return {"id": "job-next"}
        return {"id": "job-next", "status": "completed", "completed_rows": 1,
                "errors": [], "failed_rows": 0, "rejected_rows": 0}

    assert run_import(source=source, product_id="product-1", base_url="http://server",
                      state_path=state, batch_size=1, poll_interval=0,
                      skip_failed_batch=True, request_json=successful) == 0
    assert json.loads(state.read_text())["complete"] is True
    assert json.loads(state.read_text())["cursor"] == source.stat().st_size


def test_legacy_export_reads_sqlite_without_mutating_it(tmp_path):
    import sqlite3

    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript("CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT NOT NULL);"
                             "CREATE TABLE reviews (id TEXT PRIMARY KEY, product_id TEXT NOT NULL, analysis TEXT NOT NULL);")
    connection.execute("INSERT INTO products VALUES (?, ?)", ("old-1", "Laptop"))
    analysis = json.dumps({"review": {"review_text": "Great screen."}})
    connection.execute("INSERT INTO reviews VALUES (?, ?, ?)", ("review-1", "old-1", analysis))
    connection.commit()
    connection.close()
    before = database.read_bytes()

    legacy_id, name, rows = export_legacy_reviews(database)
    assert (legacy_id, name) == ("old-1", "Laptop")
    assert rows == [{"review_id": "review-1", "text": "Great screen."}]
    assert database.read_bytes() == before
