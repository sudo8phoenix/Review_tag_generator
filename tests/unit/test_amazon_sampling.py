import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts.sample_amazon import (
    MAX_METADATA_ROWS,
    MAX_REVIEW_ROWS,
    is_laptop,
    main,
    sample_streams,
)


def product(asin, *, title="Acme 14 inch Laptop", categories=None):
    return {
        "parent_asin": asin,
        "title": title,
        "categories": categories if categories is not None else ["Electronics", "Computers", "Laptops"],
        "details": '{"Brand":"Acme"}',
        "images": ["private-image"],
    }


def review(asin, text, *, timestamp=1000, **extra):
    return {
        "parent_asin": asin,
        "text": text,
        "timestamp": timestamp,
        "rating": 4.0,
        "helpful_vote": 2,
        "user_id": "sensitive-user-id",
        "images": ["sensitive-image"],
        **extra,
    }


def test_laptop_category_and_title_require_product_not_accessory():
    assert is_laptop(product("A"))
    assert is_laptop(product("A2", title="Acme Model 14"))
    assert not is_laptop(product("B", title="Laptop bag", categories=["Electronics", "Laptops", "Bags"]))
    assert not is_laptop(product("C", title="Laptop battery"))
    assert not is_laptop(product("D", categories=["Electronics", "Computers", "Monitors"]))
    assert not is_laptop(product("E", categories=[]))


def test_deterministic_selection_minimization_and_counts():
    metadata = [product("L1"), product("L2"), product("L3"),
                product("BAG", title="Laptop bag", categories=["Electronics", "Laptops", "Bags"]),
                {"title": "Laptop", "categories": ["Laptops"]}, None]
    reviews = [
        review("L1", "Great display", timestamp=1),
        review("L1", "Great display", timestamp=1),  # duplicate source event
        review("L1", "Good battery", timestamp=2),
        review("L1", "Solid keyboard", timestamp=3),
        review("L1", "Over the cap", timestamp=4),
        review("L2", "Great screen", timestamp=5),
        review("L3", "", timestamp=6),
        review("BAG", "Nice laptop bag", timestamp=7),
        review("L3", "Missing clock", timestamp=None),
        None,
    ]
    rows, summary = sample_streams(metadata, reviews, max_products=2,
                                   max_reviews_per_product=3)
    again, again_summary = sample_streams(list(reversed(metadata)), reviews,
                                         max_products=2, max_reviews_per_product=3)
    assert rows == again
    assert summary["selected_parent_asins"] == again_summary["selected_parent_asins"]
    assert summary["selected_parent_asins"][0] == "L1"  # >=3 first
    assert len(rows) == 4
    assert summary["counts"]["reviews_duplicate"] == 1
    assert summary["counts"]["reviews_over_product_cap"] == 1
    assert summary["counts"]["reviews_missing_text"] == 1
    assert summary["counts"]["reviews_missing_timestamp"] == 1
    assert summary["counts"]["metadata_missing_product"] == 1
    assert summary["counts"]["metadata_malformed"] == 1
    assert rows[0]["review_id"] == hashlib.sha256(b"L1\x001\x00Great display").hexdigest()
    assert rows[0]["brand"] == "Acme"
    assert all("user_id" not in row and "images" not in row for row in rows)


def _write_gzip(path: Path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_cli_bounded_input_manifest_hash_and_no_raw_review_in_manifest(tmp_path):
    metadata = tmp_path / "meta.jsonl.gz"
    reviews = tmp_path / "reviews.jsonl.gz"
    output = tmp_path / "sample.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_gzip(metadata, [product("L1"), product("L2")])
    _write_gzip(reviews, [review("L1", "PRIVATE REVIEW BODY", timestamp=1),
                          review("L1", "Not scanned", timestamp=2)])
    command = ["--metadata-source", str(metadata), "--reviews-source", str(reviews),
               "--output", str(output), "--manifest", str(manifest_path),
               "--metadata-rows", "1", "--review-rows", "1"]
    assert main(command) == 0
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source"]["metadata_response"]["rows_read"] == 1
    assert manifest["source"]["reviews_response"]["rows_read"] == 1
    assert manifest["source"]["metadata_response"]["stop_reason"] == "row_limit"
    assert manifest["counts"]["selected_reviews"] == 1
    assert manifest["output"]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    output_rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert manifest["counts"]["selected_reviews"] == len(output_rows)
    assert manifest["counts"]["selected_products"] == len({row["parent_asin"] for row in output_rows})
    assert manifest["selected_parent_asins"] == list(dict.fromkeys(row["parent_asin"] for row in output_rows))
    assert all(set(row) == set(manifest["output"]["fields"]) for row in output_rows)
    assert "PRIVATE REVIEW BODY" not in manifest_path.read_text()
    assert "sensitive-user-id" not in output.read_text()
    assert "L2" not in output.read_text()
    assert main(command) == 0
    assert manifest["output"]["sha256"] == json.loads(manifest_path.read_text())["output"]["sha256"]


def test_caps_reject_unbounded_scans_and_preserve_existing_output(tmp_path):
    metadata = tmp_path / "meta.jsonl.gz"
    reviews = tmp_path / "reviews.jsonl.gz"
    output = tmp_path / "sample.jsonl"
    output.write_text("original")
    _write_gzip(metadata, [product("L1")])
    _write_gzip(reviews, [review("L1", "Valid")])
    with pytest.raises(SystemExit) as first:
        main(["--metadata-source", str(metadata), "--reviews-source", str(reviews),
              "--output", str(output), "--metadata-rows", str(MAX_METADATA_ROWS + 1)])
    with pytest.raises(SystemExit) as second:
        main(["--metadata-source", str(metadata), "--reviews-source", str(reviews),
              "--output", str(output), "--review-rows", str(MAX_REVIEW_ROWS + 1)])
    assert first.value.code == second.value.code == 2
    assert output.read_text() == "original"


def test_compressed_byte_limit_is_recorded_as_the_actual_stop_reason(tmp_path):
    metadata = tmp_path / "meta.jsonl.gz"
    reviews = tmp_path / "reviews.jsonl.gz"
    output = tmp_path / "sample.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_gzip(metadata, [product("L1")])
    _write_gzip(reviews, [review("L1", "a review with enough compressed bytes", timestamp=1)])
    assert main(["--metadata-source", str(metadata), "--reviews-source", str(reviews),
                 "--output", str(output), "--manifest", str(manifest_path),
                 "--source-bytes", "24"]) == 0
    manifest = json.loads(manifest_path.read_text())
    assert manifest["selection"]["compressed_byte_limit_per_stream"] == 24
    assert manifest["source"]["metadata_response"]["stop_reason"] == "compressed_byte_limit"
    assert manifest["source"]["metadata_response"]["compressed_bytes_read"] == 24
    assert manifest["source"]["reviews_response"]["stop_reason"] == "compressed_byte_limit"
    assert manifest["source"]["reviews_response"]["compressed_bytes_read"] == 24
