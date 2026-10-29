# Temporary free Render demo

The root `render.yaml` creates exactly one **Free** Docker web service and one
**Free** PostgreSQL database in Singapore. No paid worker or persistent disk is
required: a single embedded worker processes inference sequentially.

The PostgreSQL database expires after 30 days. Export important reviews before
then. Free web services may sleep after 15 minutes without traffic and take time
to wake; they may also restart. Do not select a paid plan to remove these limits.

## Verification before deployment

On 2026-10-29 the API and embedded trained-model worker were tested inside Docker
with **512 MiB RAM and no swap**, on both Linux ARM and Linux x86 images. The five
longest reviews from the two local sourced-laptop sets were saved and analyzed
successfully without failed rows or an OOM kill. After that workload, Docker
reported roughly 451 MiB for ARM/SQLite and 426 MiB for x86/PostgreSQL. This is a
bounded smoke test, not a concurrency or production-capacity guarantee.

The PostgreSQL queue/snapshot integration test also passed against disposable
PostgreSQL 16. The image installs CPU-only PyTorch, verifies checkpoint hashes,
and hydrates Git LFS pointers from a pinned public revision if necessary.

## Deployment

Create a Render Blueprint using this public repository and its `render.yaml`.
Confirm both resources use Free. The startup script converts Render's PostgreSQL
URL to the psycopg driver format, runs migrations, then starts one Uvicorn process.

The frontend's Vercel configuration proxies `/api/*` to
`https://review-tag-generator-api.onrender.com/api/*`. Keep server credentials out
of Vite environment variables. The local `.demo` review data is not in GitHub;
import the sourced laptop review sets once the service is healthy.

Optional cloud LLM assistance is disabled in the Blueprint to avoid unapproved
provider spending. Trained extraction and sentiment inference remain enabled.
Do not describe live AI explanations as working until a provider has been
explicitly configured and verified on the hosted service.

## Scheduled health checks

`.github/workflows/demo-health.yml` checks `/api/health` every ten minutes and can
also be dispatched manually. It has read-only repository permissions and does not
need API credentials. GitHub schedules may be delayed or disabled after repository
inactivity; the check cannot guarantee that Render stays awake. One continuously
running service consumes up to 744 hours in a 31-day month, within Render's 750
workspace-hour allowance only if other free services do not consume the balance.

See https://render.com/docs/free for current restrictions.
