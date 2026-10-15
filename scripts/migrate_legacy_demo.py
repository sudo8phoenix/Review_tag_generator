#!/usr/bin/env python3
"""Read a legacy SQLite demo and enqueue its reviews into the current HTTP API.

The SQLite source is opened read-only. A JSONL snapshot is kept on disk so the
standard resumable importer can fingerprint it and safely continue after a crash.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.import_amazon import ImportErrorDetail, run_import, write_jsonl_atomic


def export_legacy_reviews(database: Path, *, legacy_product_id: str | None = None) -> tuple[str, str, list[dict]]:
    if not database.is_file():
        raise ImportErrorDetail(f"legacy SQLite database not found: {database}")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        products = connection.execute("SELECT id, name FROM products ORDER BY id").fetchall()
        if legacy_product_id is None:
            if len(products) != 1:
                raise ImportErrorDetail("select --legacy-product-id when the database has multiple products")
            legacy_product_id = str(products[0][0])
        product = next((row for row in products if str(row[0]) == legacy_product_id), None)
        if product is None:
            raise ImportErrorDetail(f"legacy product not found: {legacy_product_id}")
        records = connection.execute(
            "SELECT id, analysis FROM reviews WHERE product_id = ? ORDER BY rowid", (legacy_product_id,)
        ).fetchall()
    finally:
        connection.close()

    rows = []
    for review_id, analysis_json in records:
        try:
            analysis = json.loads(analysis_json)
            text = analysis["review"]["review_text"]
        except (TypeError, ValueError, KeyError) as exc:
            raise ImportErrorDetail(f"legacy review {review_id} has no readable review_text") from exc
        if not isinstance(text, str) or not text.strip():
            raise ImportErrorDetail(f"legacy review {review_id} has blank review_text")
        rows.append({"review_id": str(review_id), "text": text})
    return legacy_product_id, str(product[1]), rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(".demo/reviews.sqlite3"))
    parser.add_argument("--legacy-product-id")
    parser.add_argument("--product-id", required=True, help="existing product ID in the current API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--snapshot", type=Path, help="durable JSONL resume source (default beside database)")
    parser.add_argument("--state-file", type=Path, help="import resume state")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--skip-failed-batch", action="store_true")
    args = parser.parse_args(argv)
    try:
        legacy_id, name, rows = export_legacy_reviews(args.database, legacy_product_id=args.legacy_product_id)
        snapshot = args.snapshot or args.database.with_name(f"legacy-{legacy_id}-reviews.jsonl")
        expected = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")
        if snapshot.exists():
            if snapshot.read_bytes() != expected:
                raise ImportErrorDetail(f"existing migration snapshot differs from the read-only database: {snapshot}")
        else:
            write_jsonl_atomic(snapshot, rows)
        state = args.state_file or snapshot.with_suffix(snapshot.suffix + ".import-state.json")
        print(f"Read {len(rows)} reviews from legacy product {name!r}; source database opened read-only.")
        return run_import(source=snapshot, product_id=args.product_id, base_url=args.base_url,
                          state_path=state, batch_size=args.batch_size,
                          poll_interval=args.poll_interval, skip_failed_batch=args.skip_failed_batch)
    except (ImportErrorDetail, OSError, sqlite3.Error, ValueError) as exc:
        print(f"migration stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
