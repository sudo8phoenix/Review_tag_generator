#!/usr/bin/env python3
"""Import a JSONL review source into an existing demo product over HTTP.

The importer is restartable: it atomically saves the exact pending request and
its idempotency key before sending it, then advances the byte cursor only after
the batch finishes without row errors. Failed rows are exported and block later
batches until the operator explicitly accepts that failed batch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000


class ImportErrorDetail(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8") for row in rows)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _load_state(path: Path, source: Path, product_id: str, asins: tuple[str, ...], base_url: str) -> dict:
    fingerprint = sha256_file(source)
    if not path.exists():
        return {
            "version": 1,
            "source": str(source.resolve()),
            "source_sha256": fingerprint,
            "product_id": product_id,
            "asins": list(asins),
            "base_url": base_url,
            "cursor": 0,
            "source_line": 0,
            "next_batch": 1,
            "pending": None,
            "complete": False,
        }
    state = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "version": 1,
        "source": str(source.resolve()),
        "source_sha256": fingerprint,
        "product_id": product_id,
        "asins": list(asins),
        "base_url": base_url,
    }
    differences = [name for name, value in expected.items() if state.get(name) != value]
    if differences:
        raise ImportErrorDetail("resume state does not match current " + ", ".join(differences))
    return state


def _build_pending(source: Path, state: dict, batch_size: int) -> dict | None:
    cursor = int(state["cursor"])
    source_line = int(state["source_line"])
    asins = set(state["asins"])
    selected_lines: list[str] = []
    selected_source_rows: list[int] = []
    end_cursor = cursor
    end_line = source_line
    byte_count = 0
    with source.open("rb") as stream:
        stream.seek(cursor)
        while len(selected_lines) < batch_size:
            raw_line = stream.readline()
            if not raw_line:
                break
            end_cursor = stream.tell()
            end_line += 1
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ImportErrorDetail(f"source line {end_line} is not valid UTF-8; it was not skipped") from exc
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Keep malformed JSON in the batch so the API reports the exact
                # source row as rejected rather than silently losing it.
                row = None
            if asins and isinstance(row, dict) and row.get("parent_asin") not in asins:
                continue
            encoded_size = len(line.encode("utf-8"))
            if selected_lines and byte_count + encoded_size > MAX_IMPORT_BYTES - 4096:
                # The current line remains for the next batch. The cursor ends
                # at the beginning of that line, including any blank lines read.
                end_cursor -= len(raw_line)
                end_line -= 1
                break
            if encoded_size > MAX_IMPORT_BYTES - 4096:
                raise ImportErrorDetail(f"source line {end_line} exceeds the server's 10 MiB import limit")
            selected_lines.append(line if line.endswith("\n") else line + "\n")
            selected_source_rows.append(end_line)
            byte_count += encoded_size
        if not selected_lines:
            if end_cursor > cursor:
                # All remaining rows were blank or excluded by the ASIN filter.
                return {"empty": True, "start_cursor": cursor, "end_cursor": end_cursor,
                        "end_source_line": end_line}
            return None
    content = "".join(selected_lines)
    if len(content.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ImportErrorDetail("constructed batch exceeds the API's 10 MiB import limit")
    if len(selected_lines) > MAX_IMPORT_ROWS:
        raise ImportErrorDetail(f"batch exceeds the API's {MAX_IMPORT_ROWS}-row limit")
    return {
        "empty": False,
        "batch": state["next_batch"],
        "start_cursor": cursor,
        "end_cursor": end_cursor,
        "start_source_line": source_line + 1,
        "end_source_line": end_line,
        "source_rows": selected_source_rows,
        "content": content,
        "idempotency_key": str(uuid4()),
        "job_id": None,
    }


def _http_json(url: str, *, method: str = "GET", body: dict | None = None,
               idempotency_key: str | None = None, timeout: float = 30) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ImportErrorDetail(f"HTTP {exc.code} from {url}: {detail}") from exc
    except URLError as exc:
        raise ImportErrorDetail(f"request to {url} failed: {exc.reason}") from exc


def _errors_path(state_path: Path, batch: int) -> Path:
    return state_path.parent / f"{state_path.stem}.errors" / f"batch-{batch:06d}.jsonl"


def _export_errors(state_path: Path, pending: dict, job: dict) -> Path:
    source_rows = pending.get("source_rows", [])
    rows = []
    for error in job.get("errors", []):
        try:
            local_row = int(error.get("row"))
        except (TypeError, ValueError):
            local_row = None
        source_row = source_rows[local_row - 1] if local_row and 0 < local_row <= len(source_rows) else None
        rows.append({"source_line": source_row, "batch_row": local_row,
                     "status": error.get("status"), "error": error.get("error", error.get("message"))})
    if job.get("status") == "failed" and not rows:
        rows.append({"source_line": None, "batch_row": None, "status": "failed",
                     "error": job.get("error_summary") or "job failed without row-level details"})
    path = _errors_path(state_path, int(pending["batch"]))
    write_jsonl_atomic(path, rows)
    return path


def _has_row_errors(job: dict) -> bool:
    return bool(job.get("errors")) or job.get("status") in {"failed", "completed_with_errors"} \
        or int(job.get("failed_rows", 0)) > 0 or int(job.get("rejected_rows", 0)) > 0


def run_import(*, source: Path, product_id: str, base_url: str, state_path: Path,
               asins: tuple[str, ...] = (), batch_size: int = 200,
               poll_interval: float = 1.0, skip_failed_batch: bool = False,
               request_json=_http_json, sleep=time.sleep) -> int:
    if not source.is_file():
        raise ImportErrorDetail(f"source JSONL not found: {source}")
    if not 1 <= batch_size <= MAX_IMPORT_ROWS:
        raise ImportErrorDetail(f"batch size must be 1..{MAX_IMPORT_ROWS}")
    if poll_interval < 0:
        raise ImportErrorDetail("poll interval cannot be negative")
    base_url = base_url.rstrip("/")
    state = _load_state(state_path, source, product_id, asins, base_url)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    while not state["complete"]:
        pending = state.get("pending")
        if pending is None:
            pending = _build_pending(source, state, batch_size)
            if pending is None:
                state["complete"] = True
                write_json_atomic(state_path, state)
                print(f"Import complete at byte {state['cursor']}.")
                return 0
            if pending.get("empty"):
                state["cursor"] = pending["end_cursor"]
                state["source_line"] = pending["end_source_line"]
                write_json_atomic(state_path, state)
                continue
            state["pending"] = pending
            write_json_atomic(state_path, state)

        if pending.get("terminal_status"):
            if not skip_failed_batch:
                print(f"Batch {pending['batch']} has row errors exported to "
                      f"{pending['error_export']}; fix the source or pass --skip-failed-batch to continue.",
                      file=sys.stderr)
                return 2
            state["cursor"] = pending["end_cursor"]
            state["source_line"] = pending["end_source_line"]
            state["next_batch"] = int(pending["batch"]) + 1
            state["pending"] = None
            write_json_atomic(state_path, state)
            skip_failed_batch = False
            continue

        endpoint = f"{base_url}/api/demo/products/{quote(product_id, safe='')}/imports"
        if not pending.get("job_id"):
            accepted = request_json(endpoint, method="POST",
                body={"filename": "batch.jsonl", "content": pending["content"]},
                idempotency_key=pending["idempotency_key"])
            job_id = accepted.get("id") or accepted.get("job_id")
            if not job_id:
                raise ImportErrorDetail("import API response did not include a job id; pending batch was retained")
            pending["job_id"] = str(job_id)
            write_json_atomic(state_path, state)

        job_url = f"{base_url}/api/demo/jobs/{quote(pending['job_id'], safe='')}"
        while True:
            job = request_json(job_url)
            status = job.get("status")
            if status in {"completed", "completed_with_errors", "failed"}:
                break
            if poll_interval:
                sleep(poll_interval)

        if _has_row_errors(job):
            export_path = _export_errors(state_path, pending, job)
            pending["terminal_status"] = status
            pending["error_export"] = str(export_path)
            pending["error_count"] = len(job.get("errors", [])) or int(job.get("failed_rows", 0)) + int(job.get("rejected_rows", 0))
            write_json_atomic(state_path, state)
            print(f"Batch {pending['batch']} finished as {status}; exported "
                  f"{pending['error_count']} row/job errors to {export_path}.", file=sys.stderr)
            if not skip_failed_batch:
                return 2
            skip_failed_batch = True
            continue

        # Write an empty per-batch export too, so completion is auditable.
        export_path = _export_errors(state_path, pending, job)
        print(f"Batch {pending['batch']} complete: {job.get('completed_rows', 0)} reviews analyzed; "
              f"errors exported to {export_path} (empty).")
        state["cursor"] = pending["end_cursor"]
        state["source_line"] = pending["end_source_line"]
        state["next_batch"] = int(pending["batch"]) + 1
        state["pending"] = None
        write_json_atomic(state_path, state)

    print("Import complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Amazon sample JSONL file")
    parser.add_argument("--product-id", required=True, help="existing demo product UUID or ID")
    parser.add_argument("--asin", action="append", default=[], help="filter source rows by parent_asin (repeatable)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="server origin, without /api")
    parser.add_argument("--state-file", type=Path, help="resume state (default: INPUT.import-state.json)")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--skip-failed-batch", action="store_true",
                        help="explicitly accept exported row failures and continue after that batch")
    args = parser.parse_args(argv)
    state_path = args.state_file or args.input.with_suffix(args.input.suffix + ".import-state.json")
    try:
        return run_import(source=args.input, product_id=args.product_id, base_url=args.base_url,
                          state_path=state_path, asins=tuple(sorted(set(args.asin))),
                          batch_size=args.batch_size, poll_interval=args.poll_interval,
                          skip_failed_batch=args.skip_failed_batch)
    except (ImportErrorDetail, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"import stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
