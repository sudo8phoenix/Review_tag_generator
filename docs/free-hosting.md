# Free hosting alternative: Vercel and Oracle Always Free

**Historical alternative, updated 2026-10-30:** the current demo uses Vercel and
Render; see [the Render guide](render-demo.md). The unpublished-frontend note at
the end records the earlier Oracle attempt, not the current deployment status.

Deployment is not complete until the backend is reachable and the public UI has
been verified. A frontend-only deployment cannot analyze or load saved reviews.

## Account setup

Use a Vercel Hobby account and an Oracle Free Tier account. Stay on the free
account; do not upgrade to Pay As You Go. Oracle requires card verification and
may place a temporary authorization hold. Complete signup personally at
https://www.oracle.com/cloud/free/.

In the Oracle home region, request an Always Free eligible Ubuntu ARM instance:
`VM.Standard.A1.Flex`, at most **2 OCPUs / 12 GB RAM**, with a **50 GB boot volume**.
These are total tenancy allowances, so check existing allocations first. Do not
substitute a paid shape if capacity is unavailable. Confirm the console marks
the configuration Always Free eligible before creating it.

## Backend deployment prerequisites

The repository includes a Docker Compose stack with persistent PostgreSQL volumes,
a migration service, API, inference worker, and frontend reverse proxy. Follow
[the Compose instructions](getting-started.md#compose-deployment) on the VM.
The CPU-only image was built and trained-model inference smoke-tested locally on
Linux ARM on 2026-10-29. Docker now installs official CPU-only PyTorch and sets
`PYTHONPATH=/app/src` for bundled checkpoint discovery. The full PostgreSQL Compose
workflow and the actual Oracle VM still need verification; the dependency lock
was originally produced on macOS ARM.

Keep the service bound to localhost while testing. Put an authenticated HTTPS
reverse proxy in front of it before opening it to visitors: this app currently
has no user authentication and exposes saved-data deletion and review writes.
Keep the database port private. Do not publish `.env.llm` or database passwords.

Leave optional cloud AI disabled for a strictly zero-spend deployment. Existing
provider credentials do not establish that provider usage is free.

The local `.demo` reviews are not in GitHub. Export/import the two sourced laptop
review sets after deployment, or perform a deliberate database migration. Verify
30 saved reviews per laptop and matching analysis versions in the live comparison.

## Vercel frontend

Import `sudo8phoenix/Review_tag_generator` in Vercel and set **Root Directory** to
`frontend`. The checked-in `frontend/vercel.json` selects Vite, builds `dist`, and
supports direct navigation to React routes.

Once the authenticated HTTPS backend URL is known, add a rewrite for `/api/:path*`
to `https://BACKEND_HOST/api/:path*` **before** the SPA fallback in that config.
Replace BACKEND_HOST with the real hostname; never use localhost for a deployment.
The frontend already calls `/api` on its own origin, so no browser-side API keys
or cross-origin database credentials are required. Ensure the proxy authentication
flow works through the Vercel rewrite before sharing the link.

Verify `/api/health`, `/api/ready`, product listing, review preview/save, and both
comparison AI endpoints if a genuinely free provider is configured. Then add the
verified production URL to the repository README.

## Availability and cost

Oracle VMs do not have Render's 15-minute sleep behavior. Oracle can reclaim an
underused Always Free VM based on seven days of CPU/network/memory utilization;
HTTP health pings do not guarantee exemption. Do not generate artificial load.
Use Docker's existing `restart: unless-stopped` policies for process recovery.
Keep database backups outside the VM and within free storage allowances.

No keep-alive cron is needed for this design. An external uptime check can report
outages, but it cannot prevent reclamation or restore a reclaimed VM.

Reference limits, checked 2026-10-29:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/
- https://vercel.com/docs/frameworks/frontend/vite

## Deployment attempt: 2026-10-29

Vercel CLI authentication and local project linking succeeded on the Hobby
workspace. Automatic GitHub linking did not succeed; CLI deployment remains
available. No production frontend has been published.

The Oracle console rejected the Always Free A1 request (1 OCPU / 6 GB RAM) in
Hyderabad AD-1 with an out-of-capacity error. The region offered only that
availability domain. No VM was created. Retry when capacity becomes available;
do not use a paid shape or change the account plan to work around this.
