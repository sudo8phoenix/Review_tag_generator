# Managing saved reviews and imports

The product list and product insights page have two controls:

- **Clear saved reviews** removes that product's reviews, extracted mentions,
  analyses, insights, previews, jobs, import history and associated idempotency
  records, while retaining the product. It publishes a new empty snapshot.
- **Delete product** removes the product and its saved data. The initial demo
  product is seeded once and will not reappear after an intentional deletion.

Both actions open a confirmation dialog. They are rejected while the product has
queued/running jobs or active previews; wait for processing to finish and retry.
Cleanup runs in one database transaction and does not delete another product's
reviews. Product data revisions remain monotonic when clearing or removing imports.

## Remove a saved import

On the product insights page, **Saved imports** lists file batches, status, row
counts and import date. Select **Remove import**, then confirm **Remove saved
import**. Only the review rows originally inserted by that batch are removed.
The product's insight snapshots are rebuilt from the remaining saved analyses.

A duplicate-only batch inserted no review rows, so removing it leaves the existing
reviews unchanged. When a later file skipped a duplicate originally inserted by
an earlier file, deleting the earlier batch removes the original row; the skipped
copy is not retained as another independently saved review. Other batches' newly
inserted rows remain saved. Historic completed regeneration job items referencing
removed reviews are detached and marked `removed`; their counters describe the
historical job, not the product's current review total.

New imports retain the original filename as display metadata. Older data did not
store filenames and is shown as **Saved batch**. Older manual submissions also
used the generic import job type; new submissions use `review_submission` and
are not shown as file imports. No original upload is stored as a filesystem file
by the live import endpoint; it validates content and saves accepted review rows.

Removing app data does not delete original TXT/CSV files or exported JSON/CSV files
from a user's device. The app does not request or retain arbitrary device paths.

## Browser state

Successful clear/delete actions discard this product's local review/import draft
and saved job keys, including the legacy demo alias. Removing a batch clears only
browser records tied to that batch's job. Returning to the product list also
removes stale draft/job entries for products that no longer exist; drafts for
existing products are preserved.

## API and schema

| Method/path | Effect |
|---|---|
| `DELETE /api/demo/products/{id}/saved-data` | Clear saved content, keep product |
| `DELETE /api/demo/products/{id}` | Delete product and saved content |
| `GET /api/demo/products/{id}/imports` | List saved file/legacy batches |
| `DELETE /api/demo/products/{id}/imports/{job_id}` | Remove one batch's inserted reviews |

Missing products/imports return 404; active work returns 409. Batch ownership is
checked against the requested product before deletion. Clear/delete return the
product ID and number of removed reviews. Import removal also returns its job ID.

PostgreSQL deployments must run Alembic migration `0003_saved_data_management`.
It adds `application_settings` for the one-time demo seed marker and nullable
`processing_jobs.input_filename`. Existing local SQLite databases are upgraded
at repository startup, preserving their data. The initial demo seed marker is
retained when user content is deleted. Worker heartbeat records contain runtime
metadata and are not deleted by these content controls.

The app is still a local demo without authentication. These are local workspace
controls, not a tenant-aware public administration API.
