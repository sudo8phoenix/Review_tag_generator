"""Take a bounded, reproducible laptop sample from Amazon Reviews 2023.

The source streams are read sequentially and closed at their configured row and
compressed-byte limits. Only the reduced sample is written to disk.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Mapping
from urllib.request import Request, urlopen


SOURCE_ROOT = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
METADATA_URL = f"{SOURCE_ROOT}/meta_categories/meta_Electronics.jsonl.gz"
REVIEWS_URL = f"{SOURCE_ROOT}/review_categories/Electronics.jsonl.gz"
SOURCE_CARD = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
SOURCE_TERMS = f"{SOURCE_CARD}/discussions/1"
MAX_METADATA_ROWS = 500_000
MAX_REVIEW_ROWS = 1_000_000
MAX_PRODUCTS = 50
MAX_REVIEWS_PER_PRODUCT = 100
MAX_TOTAL_REVIEWS = 5_000
MAX_SOURCE_BYTES = 256 * 1024 * 1024
SEED = 42
OUTPUT_FIELDS = (
    "review_id", "parent_asin", "product_name", "category", "brand",
    "text", "rating", "helpful_votes", "timestamp",
)

LAPTOP_CATEGORY = re.compile(r"\b(laptops?|notebook computers?|chromebooks?|macbooks?)\b", re.I)
ACCESSORY_CATEGORY = re.compile(
    r"\b(accessor(?:y|ies)|cases?|sleeves?|bags?|backpacks?|chargers?|"
    r"adapters?|batteries|stands?|skins?|covers?|screen protectors?|"
    r"replacement parts?|docking stations?|cooling pads?)\b", re.I
)
ACCESSORY_TITLE = re.compile(
    r"\b(case|sleeve|bag|backpack|charger|adapter|battery|stand|skin|cover|"
    r"screen protector|replacement|dock|cooling pad)\b", re.I
)


class ByteLimitExceeded(Exception):
    """The compressed source budget ended before the next line was complete."""


class LimitedReader(io.RawIOBase):
    def __init__(self, source: BinaryIO, limit: int):
        self.source = source
        self.remaining = limit
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        if self.remaining == 0:
            raise ByteLimitExceeded
        chunk = self.source.read(min(len(buffer), self.remaining))
        count = len(chunk)
        buffer[:count] = chunk
        self.remaining -= count
        self.bytes_read += count
        return count


def _categories(row: Mapping) -> list[str]:
    value = row.get("categories")
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def is_laptop(row: Mapping) -> bool:
    """Require laptop category ancestry; reject accessory leaves and titles."""
    categories = _categories(row)
    title = row.get("title")
    if not categories or not isinstance(title, str) or not title.strip():
        return False
    if not any(LAPTOP_CATEGORY.search(category) for category in categories):
        return False
    if ACCESSORY_CATEGORY.search(categories[-1]) or ACCESSORY_TITLE.search(title):
        return False
    return True


def _brand(row: Mapping) -> str | None:
    if isinstance(row.get("brand"), str) and row["brand"].strip():
        return row["brand"].strip()
    details = row.get("details")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            return None
    if isinstance(details, dict):
        value = details.get("Brand") or details.get("brand")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rank(parent_asin: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{parent_asin}".encode()).hexdigest()


def select_candidates(rows: Iterable[Mapping], *, seed: int = SEED,
                      pool_size: int = 250) -> tuple[dict[str, dict], Counter]:
    """Keep the lowest seeded hashes among eligible metadata in bounded memory."""
    counters: Counter = Counter()
    candidates: dict[str, dict] = {}
    for row in rows:
        counters["metadata_rows_scanned"] += 1
        if not isinstance(row, dict):
            counters["metadata_malformed"] += 1
            continue
        parent = row.get("parent_asin")
        if not isinstance(parent, str) or not parent.strip():
            counters["metadata_missing_product"] += 1
            continue
        if not is_laptop(row):
            counters["metadata_non_laptop"] += 1
            continue
        parent = parent.strip()
        if parent in candidates:
            counters["metadata_duplicate_product"] += 1
            continue
        counters["eligible_metadata_rows"] += 1
        candidates[parent] = {
            "product_name": row["title"].strip(),
            "category": _categories(row),
            "brand": _brand(row),
        }
        if len(candidates) > pool_size:
            worst = max(candidates, key=lambda asin: (_rank(asin, seed), asin))
            del candidates[worst]
    return candidates, counters


def _review_id(row: Mapping, parent: str, timestamp: int | str, text: str) -> str:
    source_id = row.get("review_id")
    if isinstance(source_id, str) and source_id.strip():
        return source_id.strip()
    payload = f"{parent}\x00{timestamp}\x00{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sample_streams(metadata: Iterable[Mapping], reviews: Iterable[Mapping], *,
                   seed: int = SEED, max_products: int = MAX_PRODUCTS,
                   max_reviews_per_product: int = MAX_REVIEWS_PER_PRODUCT,
                   pool_size: int = 250) -> tuple[list[dict], dict]:
    if not (1 <= max_products <= MAX_PRODUCTS):
        raise ValueError("max_products must be 1..50")
    if not (1 <= max_reviews_per_product <= MAX_REVIEWS_PER_PRODUCT):
        raise ValueError("max_reviews_per_product must be 1..100")
    if not (max_products <= pool_size <= 1000):
        raise ValueError("pool_size must be between max_products and 1000")

    candidates, counts = select_candidates(metadata, seed=seed, pool_size=pool_size)
    by_product: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for row in reviews:
        counts["review_rows_scanned"] += 1
        if not isinstance(row, dict):
            counts["reviews_malformed"] += 1
            continue
        parent = row.get("parent_asin")
        if parent not in candidates:
            counts["reviews_outside_candidate_pool"] += 1
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            counts["reviews_missing_text"] += 1
            continue
        timestamp = row.get("timestamp", row.get("sort_timestamp"))
        if not isinstance(timestamp, (int, str)) or isinstance(timestamp, bool):
            counts["reviews_missing_timestamp"] += 1
            continue
        rating = row.get("rating")
        if not isinstance(rating, (int, float)) or isinstance(rating, bool) or not 1 <= rating <= 5:
            counts["reviews_invalid_rating"] += 1
            continue
        helpful = row.get("helpful_vote", row.get("helpful_votes", 0))
        if not isinstance(helpful, int) or isinstance(helpful, bool) or helpful < 0:
            helpful = 0
            counts["reviews_invalid_helpful_votes"] += 1
        review_id = _review_id(row, parent, timestamp, text)
        if review_id in seen:
            counts["reviews_duplicate"] += 1
            continue
        if len(by_product[parent]) >= max_reviews_per_product:
            counts["reviews_over_product_cap"] += 1
            continue
        seen.add(review_id)
        product = candidates[parent]
        by_product[parent].append({
            "review_id": review_id,
            "parent_asin": parent,
            "product_name": product["product_name"],
            "category": product["category"],
            "brand": product["brand"],
            "text": text,
            "rating": rating,
            "helpful_votes": helpful,
            "timestamp": timestamp,
        })

    eligible = [asin for asin, records in by_product.items() if len(records) >= 3]
    small = [asin for asin, records in by_product.items() if len(records) < 3]
    selected = (sorted(eligible, key=lambda asin: (_rank(asin, seed), asin)) +
                sorted(small, key=lambda asin: (_rank(asin, seed), asin)))[:max_products]
    output = [row for asin in selected for row in by_product[asin]]
    assert len(output) <= MAX_TOTAL_REVIEWS
    counts["candidate_products"] = len(candidates)
    counts["selected_products"] = len(selected)
    counts["selected_reviews"] = len(output)
    counts["selected_products_with_three_reviews"] = sum(len(by_product[asin]) >= 3 for asin in selected)
    return output, {"counts": dict(sorted(counts.items())), "selected_parent_asins": selected}


def _json_lines(rows: Iterable[Mapping]) -> bytes:
    return b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8") for row in rows)


def _bounded_records(source: str, *, max_rows: int, max_bytes: int,
                     details: dict) -> Iterator[dict | None]:
    """Open a local JSONL[.gz] file or HTTPS gzip stream and stop at both bounds."""
    if source.startswith("https://"):
        handle = urlopen(Request(source, headers={"User-Agent": "review-tag-generator-research-sampler/1"}), timeout=30)
    else:
        handle = open(source, "rb")
    with contextlib.closing(handle):
        details["etag"] = handle.headers.get("ETag") if hasattr(handle, "headers") else None
        details["last_modified"] = handle.headers.get("Last-Modified") if hasattr(handle, "headers") else None
        limited = LimitedReader(handle, max_bytes)
        with io.BufferedReader(limited) as buffered:
            stream = gzip.GzipFile(fileobj=buffered) if source.endswith(".gz") else buffered
            with contextlib.closing(stream):
                for index in range(max_rows):
                    try:
                        line = stream.readline()
                    except ByteLimitExceeded:
                        details["stop_reason"] = "compressed_byte_limit"
                        break
                    if not line:
                        details["stop_reason"] = "source_eof"
                        break
                    details["rows_read"] = index + 1
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        value = None
                    yield value
                else:
                    details["stop_reason"] = "row_limit"
        details["compressed_bytes_read"] = limited.bytes_read


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary_name = Path(temporary.name)
    temporary_name.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-source", default=METADATA_URL)
    parser.add_argument("--reviews-source", default=REVIEWS_URL)
    parser.add_argument("--output", type=Path, default=Path("data/amazon/laptop_reviews.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("audit/evidence/current/amazon-manifest.json"))
    parser.add_argument("--metadata-rows", type=int, default=MAX_METADATA_ROWS)
    parser.add_argument("--review-rows", type=int, default=MAX_REVIEW_ROWS)
    parser.add_argument("--source-bytes", type=int, default=MAX_SOURCE_BYTES)
    parser.add_argument("--products", type=int, default=MAX_PRODUCTS)
    parser.add_argument("--reviews-per-product", type=int, default=MAX_REVIEWS_PER_PRODUCT)
    parser.add_argument("--candidate-pool", type=int, default=250)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    if not 1 <= args.metadata_rows <= MAX_METADATA_ROWS or not 1 <= args.review_rows <= MAX_REVIEW_ROWS:
        parser.error("row limits must be positive and no greater than 500000/1000000")
    if not 1 <= args.source_bytes <= MAX_SOURCE_BYTES:
        parser.error("source-bytes must be positive and no greater than 268435456")
    if args.output.resolve() == args.manifest.resolve():
        parser.error("output and manifest must have different paths")
    if not args.metadata_source.startswith("https://") and not Path(args.metadata_source).is_file():
        parser.error("metadata source must be an existing file or HTTPS URL")
    if not args.reviews_source.startswith("https://") and not Path(args.reviews_source).is_file():
        parser.error("review source must be an existing file or HTTPS URL")

    meta_info: dict = {"rows_read": 0}
    review_info: dict = {"rows_read": 0}
    try:
        metadata = _bounded_records(args.metadata_source, max_rows=args.metadata_rows,
                                    max_bytes=args.source_bytes, details=meta_info)
        reviews = _bounded_records(args.reviews_source, max_rows=args.review_rows,
                                   max_bytes=args.source_bytes, details=review_info)
        rows, summary = sample_streams(metadata, reviews, seed=args.seed,
                                       max_products=args.products,
                                       max_reviews_per_product=args.reviews_per_product,
                                       pool_size=args.candidate_pool)
    except (OSError, ValueError, EOFError) as error:
        print(f"sampling failed: {error}", file=sys.stderr)
        return 1

    payload = _json_lines(rows)
    manifest = {
        "schema_version": 1,
        "source": {"name": "McAuley Lab Amazon Reviews 2023", "card": SOURCE_CARD,
                   "usage_statement": SOURCE_TERMS, "category": "Electronics",
                   "metadata_url": args.metadata_source, "reviews_url": args.reviews_source,
                   "revision": "unversioned upstream files; ETag/Last-Modified captured below",
                   "metadata_response": meta_info, "reviews_response": review_info},
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection": {"seed": args.seed, "rank": "SHA-256(seed:parent_asin), ascending",
                      "candidate_pool": args.candidate_pool,
                      "rule": "lowest-hash eligible metadata candidates; prefer >=3 valid reviews; "
                              "then seeded hash order; first valid reviews in source order",
                      "metadata_row_limit": args.metadata_rows, "review_row_limit": args.review_rows,
                      "compressed_byte_limit_per_stream": args.source_bytes,
                      "max_products": args.products,
                      "max_reviews_per_product": args.reviews_per_product,
                      "max_total_reviews": MAX_TOTAL_REVIEWS},
        **summary,
        "output": {"path": str(args.output), "sha256": hashlib.sha256(payload).hexdigest(),
                   "bytes": len(payload), "fields": list(OUTPUT_FIELDS),
                   "review_id_method": "source review_id if present; otherwise SHA-256 of "
                                       "parent_asin + NUL + original timestamp + NUL + original text"},
        "limitations": ["Category/title heuristic may miss laptops with absent or unusual metadata.",
                        "Sample is an unlabelled convenience subset, not representative of Amazon.",
                        "Star ratings are metadata, not gold aspect sentiment labels."],
    }
    _write_atomic(args.output, payload)
    _write_atomic(args.manifest, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
    print(json.dumps({"selected_reviews": len(rows), "selected_products": summary["counts"]["selected_products"],
                      "sha256": manifest["output"]["sha256"], "output": str(args.output),
                      "manifest": str(args.manifest)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
