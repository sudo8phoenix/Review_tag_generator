# Amazon Reviews 2023 demonstration sample

`scripts/sample_amazon.py` prepares an **unlabelled, bounded laptop review sample** for
the later batch demo. It does not train the A2/A3 models. Star ratings remain optional
metadata; they are not gold labels for aspect sentiment.

## Official source and use

The source is McAuley Lab's [Amazon Reviews 2023 project](https://amazon-reviews-2023.github.io/)
and its [dataset card](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023).
The sampler streams the official [Electronics metadata](https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Electronics.jsonl.gz)
and [Electronics reviews](https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Electronics.jsonl.gz).
The project describes `categories` as a hierarchy and says `parent_asin` links reviews
to product metadata. It does not provide a standalone Computers domain. The direct
UCSD gzip files do not have an immutable published revision; each completed run
records the HTTP ETag and Last-Modified headers plus retrieval time. Those headers
are provenance hints, not a guarantee that the source content cannot change.

In the [maintainers' license discussion](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1),
McAuley Lab says it cannot assign a license to the reviews and made them available
primarily for research. No click-through license acceptance is stated on these
public files. Do not treat this as a grant for commercial use or redistribution.
Assess the intended use before publishing any real review text or product demo.
Keep all sampled review text in the ignored `data/amazon/` directory.

## Run

From the repository root, with Python 3.11:

```bash
python3 scripts/sample_amazon.py
```

This reads gzip streams directly, stops after at most 500,000 metadata rows and
1,000,000 review rows, and also limits each compressed transfer to 256 MiB.
It does not save the source archives. It keeps at most 250 laptop metadata
candidates in memory, ranked by SHA-256 of `42:parent_asin`; the final sample has
at most 50 products and 100 reviews per product (5,000 overall). Products with
at least three valid reviews get priority within that candidate pool. The
sampler requires **laptop category ancestry** and rejects accessory branches
and accessory titles. Missing or unusual metadata can
cause true laptops to be missed. This is a convenience sample, not a random or
representative draw from the whole Amazon collection.

Outputs when the command completes:

- `data/amazon/laptop_reviews.jsonl`: local sampled reviews (ignored by Git).
- `audit/evidence/current/amazon-manifest.json`: source URLs, retrieval time,
  headers, stop reasons, selection rules, exact counts and JSONL SHA-256. It
  contains selected product IDs and field names but no review text.

The review output retains only `review_id`, `parent_asin`, `product_name`,
`category`, `brand` when present, `text`, `rating`, `helpful_votes`, and
`timestamp`. The source typically has no review ID. In that case the sampler
uses SHA-256 of the exact source `parent_asin`, a NUL separator, original
timestamp, another NUL separator, and original review text. `user_id`, images,
reviewer profiles, purchase verification and unrelated metadata are dropped.
Duplicate derived IDs are excluded; the manifest reports malformed, missing,
duplicate and over-cap rows separately.

The scan caps can produce **fewer than 5,000** reviews or zero. Do not loosen
the category criterion, silently continue into unrelated categories, or report
5,000 unless the manifest confirms it. A zero or small result is a valid
coverage finding under these limits.

For a controlled local input or a smaller trial, use gzip or plain JSONL files:

```bash
python3 scripts/sample_amazon.py \
  --metadata-source /path/to/meta_Electronics.jsonl.gz \
  --reviews-source /path/to/Electronics.jsonl.gz \
  --metadata-rows 10000 --review-rows 20000
```

The script never needs an Amazon account, Kaggle token or Hugging Face dataset
loader. It accepts public HTTPS URLs and local files. Re-run only when a fresh
sample is desired; the manifest and output are replaced together after a
successful scan. Verify them with the manifest's `output.sha256` and exact
`counts.selected_reviews` value.
