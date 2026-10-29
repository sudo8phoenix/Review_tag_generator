# Shopping companion: design and implementation

Updated **30 October 2026**. This implementation connects a Chrome side panel to the hosted or local review service and gives the web app a shopping-focused navigation and evidence layout.

Actual UI captures: [saved feature/evidence view](assets/portfolio/shopping-evidence.png) and [built Chrome companion](assets/portfolio/shopping-extension.png). Both use synthetic reviews and the explicitly labeled heuristic backend. They demonstrate the interface and local workflow, not trained-model accuracy.

## Design references

The references were selected for specific interactions that fit this product:

| Reference | Pattern adopted | Where it appears |
|---|---|---|
| [Honey Droplist](https://help.joinhoney.com/article/79-what-is-droplist) | Save an item while browsing and revisit it later | Extension capture/inspect/save flow connected to saved web products |
| [Raindrop.io](https://raindrop.io/) and its [official preview image](https://raindrop.io/_next/static/media/preview.ce50e8c9.png) | A searchable collection with an adjacent item preview | Compact saved-product rows and feature feedback beside source evidence |
| [RTINGS comparison](https://www.rtings.com/headphones/tools/compare) | Compare attributes in aligned rows and keep their supporting methodology available | Dedicated two-product comparison with visible support counts and expandable provenance |

The design interpretation is specific to this application: preserve its green/gray foundation, add a restrained serif heading to editorial/companion areas, use compact rows and clear type hierarchy, and make the original review the next step after a finding. Prices, cashback, lab scores, and product photographs are outside the implemented data model.

## What changed

- **Saved products:** searchable collection, URL-backed search, direct analysis/import/comparison links, and product creation.
- **Product overview:** feature feedback and source reviews in one layout; selectable features and sentiment filters persist in the URL. Review-vote filtering treats contradictory positive/negative mentions as neutral, matching aggregation semantics.
- **Focused destinations:** Review evidence, Advanced tools, and Data settings have their own routes. Corrections, annotations, import removal, and deletion retain their existing behavior. Destructive controls live in Data settings.
- **Comparison:** separate `/compare` page, retained selected starting product, and expandable snapshot/model identifiers.
- **Chrome companion:** actual unpacked Manifest V3 extension, local service settings, selected-text capture, pasted batches, an experimental Amazon adapter, unsaved summaries, explicit save, restart recovery, row errors, and failed-row retry.
- **Temporary summaries:** a new backend endpoint reuses the saved-analysis aggregation policy. It checks product membership, preview completion, expiry, and pipeline version, and deduplicates text using the same normalized key as saving.
- **Developer tooling:** patched Vite/Vitest and a transitive source-map dependency following the dependency audit; CI now builds the extension before browser checks.

Existing product overview, single-review, import, and model routes remain available. Raw reviews moved to `/products/:id/reviews`, evaluation/annotation to `/products/:id/advanced`, and data controls to `/products/:id/settings`.

## Build and install the extension

The [extension source guide](../frontend/extension/README.md) lists the tracked files
and troubleshooting steps. Chrome **116 or newer** is required. From a cloned
repository, install the frontend dependencies and build (Python and model downloads
are needed only if you also run the backend locally):

```bash
npm --prefix frontend ci
npm --prefix frontend run build:extension
```

1. Open `chrome://extensions` in Chrome and enable Developer mode.
2. Choose **Load unpacked**, then select `frontend/dist-extension` in this project.
3. Pin the extension and invoke it from the toolbar on the page you want to inspect.
4. Open **Connection settings** in the panel. Fresh installs default to `https://review-tag-generator.vercel.app`; previously saved settings are retained. For a private local backend, follow [getting started](getting-started.md), select **Localhost (127.0.0.1)**, and use API port **8000** and workspace port **5173** (or your actual ports).
5. Capture a complete selected review, paste reviews separated by blank lines, or try loaded-review capture on Amazon.com / .in, Flipkart, Walmart, Best Buy, or Target.
6. Choose or explicitly create a destination product. **Save captured reviews** stores the reviews immediately and queues analysis without requiring preview. Alternatively, preview and inspect the feature quotes first. **Download captured reviews (.txt)** exports the captured text without contacting the API.
7. Wait for processing; **Open saved products** opens the same saved product in the web app.

Rebuild and reload the unpacked extension after source changes. A build is also required before running the extension browser test. For the isolated visual preview used during this implementation, the API ran on **8017** and the workspace on **5173**; those are test/demo ports, not new defaults.

### Behavior and boundaries

Capture/paste is limited to 100 reviews per batch, with 10,000 Unicode code points per review. Previewing stores temporary server-side preview rows; it does not add reviews to published totals. Creating a product explicitly creates an empty durable product. Saving records a durable processing job and the raw reviews, even while analysis is pending. Repeated preview requests reuse unexpired exact-text previews for the same product and pipeline version, so retries do not fill the queue with duplicate work. The panel shows preview progress and permits up to 30 minutes for LLM-assisted batches.

The panel persists connection settings and one pending save’s product ID/name, review text, request key, and job ID in Chrome local storage. This permits recovery after a lost response or panel restart. Completed jobs remove that recovery record. Captures/previews otherwise stay in panel memory; they do not survive closing it. Source-page titles/URLs are not added to the server’s product model in this version.

The extension requests `sidePanel`, `activeTab`, `scripting`, and `storage`, with service host access to `http://127.0.0.1/*`, `https://*.vercel.app/*`, and `https://*.onrender.com/*`. The extension CSP permits connections to these same service origins. Explicit HTTPS host permissions for Amazon.com / .in, Flipkart, Walmart, Best Buy, and Target let the panel capture loaded reviews without depending on a temporary toolbar grant. Other sites still require invoking the toolbar icon on that page before selected-text capture. After updating, rebuild and reload the extension at `chrome://extensions`; allow shopping site access if Chrome prompts. It reads page content only after capture is invoked, bundles executable code locally, and has no remote-provider calls of its own. See [Chrome activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab), [Side Panel API](https://developer.chrome.com/docs/extensions/reference/api/sidePanel), and [cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests) for the platform behavior behind this implementation.

The retailer adapters check the host, read loaded review-body elements, skip hidden/clipped/collapsed bodies, bound the batch, and perform no pagination or crawling. They have fixture coverage; live retailer layouts, regional variants, and expansion behavior have **not** been validated. Selection and paste are the supported fallbacks. A tab/page change cancels source-bound capture/preview and clears the destination choice; a submitted job retains its original product and text for recovery.

The app has no user authentication or per-user data isolation; the hosted demo shares saved data. Use local mode for private reviews. Chrome Web Store distribution, hosted authentication, personal account synchronization, persistent retailer product identity, and broad live-site capture are future work. Existing trained models remain available through the standard launcher; the browser suite uses an explicitly labeled heuristic backend with synthetic reviews.

## Verification and fixes

Bug 1: [🟡 medium] Cancel capture when tab discovery becomes stale — `frontend/src/extension/CompanionPanel.tsx:150`

Row: Table 7, C6. A tab switch could occur before the active-tab query returned and before capture had registered ownership. Capture now reserves ownership before that await, checks the generation immediately afterward, and checks the returned source URL. The real-extension test delays only tab discovery, switches tabs, and verifies that no script read occurs; analysis/storage calls in that test remain real.

Bug 2: [🟡 medium] Isolate review drafts when the product route changes — `frontend/src/routes/pages.tsx:360`

Row: Table 2, S3; Table 7, C5. The old shared form instance could retain text when the product parameter changed and no destination draft existed. Review/import forms now remount by product ID. A browser regression switches between two product routes and verifies that their drafts remain separate.

The mobile visual pass also found a wrapping flex form that placed the submit button outside a 375 px viewport. It now uses explicit grid tracks; product rows also use bounded columns. The extension folds its input steps once a summary is ready so results stay accessible without repeating setup.

Bug 3: [🟡 medium] Release recovery when the saved job was removed — `frontend/src/extension/CompanionPanel.tsx:137`

Row: Table 2, S12; Table 7, C6. Deleting a completed product or batch can remove its job while the panel is closed. A recovered 404 previously looked like a transient disconnection and left all inputs locked. The transport now preserves HTTP status; the panel stops polling missing jobs and lets the user clear only the browser's stale recovery record. The Chrome test reproduces a removed product/job and checks that the panel can start another capture.

The dependency advisory check initially reported five affected development-tool packages. Vite **7.3.7**, Vitest **4.1.12**, and the compatible source-map patch resolve the lockfile’s reported advisories. The final npm audit reports **0 vulnerabilities**. This describes the registry check; it is not a claim that every dependency is free of defects.

| Check | Result |
|---|---|
| Python non-model suite | 321 passed, 2 skipped, 7 model tests deselected |
| Frontend unit tests | 11 passed |
| Browser workflows | 23 passed; shopping/extension regressions rerun after the final recovery fix |
| Lint and TypeScript | Passed |
| Web and extension production builds | Passed |
| Layout | Five key web routes checked at 320, 768, 1024, and 1440 px; actual extension at 320 and 390 px |
| Chrome extension integration | Real manifest, storage, local API, unsaved preview, lost-response replay after reload; captured total stays at three reviews |
| Review-agent final diff pass | No findings. Local change is coherent; live retailer/provider/PostgreSQL/deployment checks remain outside the verified scope. |

The [seven-table audit index](shopping-audit.md) covers 36 registered API paths, state machines, timers, numeric bounds, data flows, resources, and concurrency. Local tests cover intake, evidence, corrections, annotation, deletion, replay, and recovery. The index marks live PostgreSQL concurrency/migrations, live provider transport, production rate/load behavior, retailer variations, and deployment/store distribution **unverified**. No production requests, public deployment, paid provider calls, or changes to the user’s saved demo database were part of this work. This is not an exhaustive production security certification.

## Hosted companion connection

Fresh installs of extension version 0.1.1 default to `https://review-tag-generator.vercel.app`.
Connection settings can switch to local loopback or a Vercel/Render HTTPS origin.
The manifest grants the matching host permissions and connection policy; rebuild
with `npm --prefix frontend run build:extension`, then click **Reload** for the
unpacked extension in `chrome://extensions` after updating. Reopen its side panel
to replace an already-running copy. Old CSP errors can remain in the browser error
list even after reloading; verify new requests and the connected status.

Free Render backends may take time to wake. The panel retries automatically and
preserves interrupted-save recovery. A submitted review can be saved while its
analysis waits behind an import; inspect Save progress until it completes.

Run hosted end-to-end checks explicitly with:

```bash
LIVE_DEMO_URL=https://review-tag-generator.vercel.app npm --prefix frontend run test:e2e -- hosted-demo.spec.ts
```

These checks create disposable QA products and remove them when no work is active.
The retailer capture fixture is controlled test HTML; its preview and save requests
use the real hosted trained-model API. This does not establish that every live
retailer layout is supported.
