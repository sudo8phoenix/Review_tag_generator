# Frontend and packaging proposal

**Status:** Shopping-first direction confirmed; initial implementation started at your request. See the [implementation and verification guide](shopping-companion.md).

**Date:** 27 October 2026.

**Scope:** Original product ideation and design direction. The subsequent local implementation is recorded separately; no publication has occurred.

**Visual companion:** [Open the interactive concept board](frontend-concept.html). Download/open the HTML in a browser if your editor displays its source. All sample reviews, counts, and outputs in that board are illustrative.

## Recommendation

Build **one shopping companion with two connected surfaces**: a **Chrome extension for understanding reviews while browsing**, and a **web app for saved products, comparisons, and deeper evidence**. Prioritize the extension's shopping experience and reuse the existing web app and analysis backend.

The product promise should be: **“Understand the strengths and recurring complaints before you buy.”** Every feature-level finding should link to its supporting review text and show how many captured reviews support it.

The core journey is **browse a product → analyze available reviews → inspect strengths and complaints → save the product → compare saved options on the web**. Both surfaces share product identities and saved analysis. Shoppers should be able to get useful feedback in the extension without opening the web app first.

Your preference establishes shoppers as the primary audience; researchers and annotators remain secondary users. Whether shoppers find the flow useful still needs testing. The first engineering gate should prove capture and product matching on one retailer before promising broad site support. A one-review capture is a technical experiment; the first useful shopping release should handle multiple complete reviews and expose coverage limits.

### What each surface owns

| Extension — primary shopping experience | Web app — saved-product companion |
|---|---|
| Recognize a supported product page after invocation | Browse saved products and their saved evidence |
| Capture a bounded set of available complete reviews | Compare two saved products by feature |
| Show feature strengths, recurring complaints, and supporting counts | Inspect larger evidence sets and analysis provenance |
| Open source quotes and see exactly which sample was analyzed | Add reviews through paste or imports when needed |
| Save the product and its captured reviews | Keep annotation and model tools under Advanced |

Product recognition, capture adapters, provenance storage, and any personal shortlist are proposed additions. The current backend already provides much of the analysis and two-product comparison, but it does not implement those shopping-specific features. Browser extension packaging itself does not require a web workspace; the web app earns its place through continuity and comparison.

## What the project already gives us

The repository already contains React 19, TypeScript, Vite, React Router, Tailwind 4, custom CSS tokens, Recharts, and a FastAPI/Python worker backend. It supports preview/save, product insights, bounded file imports, evidence inspection, product comparison, optional cited Q&A, corrections, and a full annotation workspace.

The existing muted green, warm gray, and evidence-highlighting language is a sensible foundation. Preserve that identity and improve hierarchy rather than introducing a new framework or an unrelated aesthetic.

Two structural problems matter more than adding decoration:

- **Product detail is doing too much.** Insights, saved-data controls, imports, assistant, robustness, quality queue, annotation, comparison, and individual reviews are composed in one long route. The historical [evidence-tools screenshot](assets/portfolio/evidence-tools.png) makes the scrolling cost visible; current source contains additional annotation controls.
- **Navigation promises destinations that converge.** “Products,” “Review analyzer,” and “Imports” currently link to `/products`; the latter two ask the user to choose a product again. Navigation should retain a selected product and go directly to its tool.

The backend supplies source spans and snapshot provenance, which are unusually valuable design material. Clicking an insight should lead directly to its supporting text. There is no implemented retailer URL-fetching or automatic review-collection service in the inspected API. The current app is a local, unauthenticated demo; a polished interface does not establish public-service readiness.

Evidence inspected: [app shell](../frontend/src/components/AppShell.tsx), [page composition](../frontend/src/routes/pages.tsx), [API shapes](../frontend/src/api.ts), [architecture](architecture.md), [current API](api.md), [release status](release-status.md), and existing screenshot assets. This is a design assessment from source and saved captures, not a new end-to-end audit of the running application.

## Who the interface should serve

| User hypothesis | Main job | Best surface |
|---|---|---|
| **Shopper — primary** | Understand repeated feature feedback while browsing and save options | **Shopping extension** |
| Shopper returning to saved options | Compare products and inspect the evidence behind a decision | Web companion |
| Product researcher, seller, or student demonstrating the system | Import feedback, find repeated strengths/problems, check evidence | Advanced web tools |
| Annotator or model evaluator | Correct spans and labels, resolve ambiguity, export decisions | Dedicated workspace view |

These jobs share data but need different levels of detail. Lead with strengths, complaints, evidence counts, and saved products. Keep annotation and model diagnostics in Advanced so the shopping journey remains focused.

## Packaging options

The fit and effort labels below are judgments based on this repository, not measured estimates.

| Option | Why choose it | Tradeoff | Fit / incremental effort |
|---|---|---|---|
| Improve the existing web app alone | Reuses the current architecture; room for evidence and comparison | User switches away from the retailer page; misses the desired shopping entry point | Useful foundation / medium |
| **Shopping extension + connected web app** | Feedback while browsing, followed by saved-product comparison | Two UI surfaces, capture adapters, shared product identity, connection lifecycle, store maintenance | **Recommended package / medium–large** |
| Extension as the whole product | Focused shopping-context experience | Less room for larger evidence sets and comparisons; still needs inference service | Possible, but does not meet the preference for both surfaces / large |
| Installable PWA | Separate app window and launcher without a separate native UI | Installation does not make Python inference run offline or let the app read other sites | Useful convenience later / small–medium |
| Desktop wrapper with local backend | More integrated local/private installation | Must package Python, models, startup, updates, and per-platform distribution | Defer until offline installation is a real requirement / large |
| Embedded retailer widget or API product | Could fit a seller-owned store or another application's workflow | Requires a distribution partner/integration, access controls, and another support surface | Future direction / large |

A PWA can provide a standalone window, with install behavior varying by browser/platform; offline inference would require separate engineering. See [web.dev installation guidance](https://web.dev/learn/pwa/installation).

**Why the extension is not automatically the simpler option:** the trained Python checkpoints are approximately 508 MB according to the project README. Putting a UI in an extension does not move that pipeline into the browser. Browser inference would be a separate model-conversion and evaluation project. The practical first extension calls the existing backend.

## Three visual directions

### A. Evidence workspace — web companion

Calm, compact, light interface: warm gray canvas, white work areas, forest/teal actions, restrained borders, clear tables, and highlighted source text. A selected product stays visible in navigation. The main view pairs a feature list with a source-evidence pane.

This supports deeper inspection after a shopper saves a product. Preserve the current design investment while simplifying primary navigation around Saved products and Compare.

### B. Shopping lens — recommended primary experience

A narrow side panel with the current product, **Analyze available reviews**, feature strengths, recurring complaints, support counts, and expandable quotes. Make **Save product** the next step after inspection and provide a route to saved-product comparison on the web. Explain the sample coverage beside the result.

This leads the combined product. Share typography, sentiment labels, colors, and evidence components across both surfaces so the transition feels continuous.

### C. Annotation desk

A dense three-pane layout: review worklist, source text with selectable spans, and editable labels/history. Put review status and “Save draft / Mark reviewed” within reach. Keep model prediction and reviewer decision visually separate.

Best for sustained evaluation work. Make it a dedicated mode rather than the everyday landing page. This direction can reuse the existing annotation components.

## Proposed web companion

### Navigation and screens

Keep shopper navigation small: **Saved products**, **Compare**, and **Advanced**. Within a product, lead with **Overview** and **Review evidence**. Put manual analysis, imports, annotation, model evaluation, and data settings in Advanced. Product-specific tools retain the current product ID. The retailer page is the main capture destination; the web app holds the saved evidence and comparison workflow.

Suggested routes, subject to implementation review:

```text
/products                         Product library
/products/:id                     Overview
/products/:id/reviews             Searchable evidence browser
/products/:id/review              Analyze; retain the existing URL
/products/:id/upload              Imports; retain the existing URL
/products/:id/annotations         Review worklist and annotation desk
/products/:id/settings            Saved imports and data removal
/compare?left=…&right=…           Two-product comparison
/models                           Model and evaluation details
```

“Analyze review” from the product library should choose a product once and proceed. Avoid three sidebar links returning users to the same library. Retain compatible links while refactoring routes.

### Product library

Use a compact saved-product list with name, source retailer/link when recorded, captured-review count, and **Open evidence** or **Compare**. Offer **Add reviews manually** as a fallback and **Try sample products** for demos. A sample action must identify synthetic inputs and the actual backend mode. An authenticated personal shortlist and source links require additions to the current local product model; avoid implying those already exist.

### Saved-product overview

At desktop widths:

```text
┌ Product selector / current product ───── Analyze review / Import ┐
│ Overview   Review evidence   Compare   Advanced                   │
│ Published evidence status · saved-review count                   │
├ Feature feedback ───────────────────┬ Supporting evidence ───────┤
│ Display       +11 / 1 neutral / −2 │ Selected feature + support   │
│ Battery        +3 / 1 neutral / −8 │ Source quote with highlight │
│ Keyboard       +6 / 1 neutral / −1 │ Sentiment + original phrase │
│ Choose a row to inspect evidence  │ Open full review            │
└───────────────────────────────────┴─────────────────────────────┘
```

These are fictional layout numbers. The UI should use backend classifications and support gates, rather than reimplementing the aggregation formula.

The first viewport should answer: **Which features receive recurring feedback? How many saved reviews support it? What did someone actually write?** Use one feature table with compact sentiment bars and explicit counts. Avoid presenting the same distribution as both a large chart and a duplicate table above the fold.

Select an aspect to filter its source reviews in the adjacent pane. The default excerpt is representative, not proof of unanimity; provide positive, neutral, and negative filters with counts. Open exact mention details in a drawer. Move data deletion into settings and robustness into an expandable evidence tool.

### Analyze

Two columns: review input on the left, highlighted preview and detected aspects on the right. Before input, offer a clearly labeled synthetic example. Preserve **Preview analysis → Inspect results → Save review → Processing → Published insights**.

Keep “Not saved” visible until the explicit save. Editing input invalidates the displayed preview for saving. Expired previews require a fresh preview. A save queues processing; show the returned job state instead of immediately increasing published totals. No-aspect results should be valid, understandable outcomes.

### Imports

Give imports a dedicated flow: choose file/paste → validate → inspect accepted/rejected rows → confirm import → processing → published result. Preserve existing limits and formats. Make duplicate counts and downloadable row errors visible. Keep batch removal in data settings with its existing confirmation behavior.

### Compare

Compare two saved products by canonical feature. Put support counts next to each distribution, then the observed feedback difference. Display insufficient evidence and pipeline mismatch explicitly. A stronger sentiment balance is not a “best product” verdict. Start with the existing comparison API; postpone multi-product ranking.

### Review and annotate

Separate worklist and editor, retain draft/conflict handling, and put original predictions beside reviewer changes. The UI must state that corrections and annotations do not automatically update model totals or train the model. The existing annotation and correction components are reusable foundations.

## Shopping extension — the main experience

Use a **Manifest V3 side panel** opened by a toolbar action; a panel can sit beside the web page and has more room for reading than a small action popup. Chrome documents this surface in its [Side Panel API](https://developer.chrome.com/docs/extensions/reference/api/sidePanel). Chrome is the initial target; other browsers need a separate capability and packaging check.

Proposed user-facing first release, after the capture feasibility gate:

1. Open a product page on the initial supported retailer and invoke the extension.
2. Confirm the detected product and choose **Analyze available reviews**. Use one validated retailer adapter to capture a bounded set of complete reviews; allow manual paste/capture when extraction fails.
3. Show how many reviews were captured and the capture scope, such as **3 reviews currently displayed**. Avoid implying that the retailer's full review corpus was analyzed.
4. Preview feature strengths and complaints with supporting counts and quotes. Clearly identify whether the text goes to a local service or a hosted service. Results below the support threshold remain individual observations rather than recurring tags.
5. Choose **Save product** to persist the product and captured reviews. Track processing before showing published results, then offer **Open saved products / Compare** on the web.

The shopping summary for an unsaved batch is a proposed addition: today's API returns mention-level previews, while product aggregates are published after saving. Decide an explicit temporary-batch aggregation contract for the extension, reusing the backend's aggregation rules and support gate. Do not fake a product aggregate from one review or silently persist captures on Analyze.

Each complete captured review becomes a separate analysis source. Preserve its text after capture and convert browser UTF-16 selection indices to the backend's Unicode code-point offsets where selections are used. Collapsed or truncated review snippets should be flagged or skipped; partial text can omit sentiment context. Retain the manual fallback.

For the first capture feature, consider `sidePanel`, `activeTab`, and `scripting`; request `storage` only for settings or recoverable job IDs that actually need it. A right-click entry point would additionally need `contextMenus`. `activeTab` grants temporary access following a user gesture, and script injection also needs `scripting`; see [Chrome's activeTab documentation](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab). Limit backend host access to the configured service. The store requires the narrowest permissions needed for current functionality: [permissions policy](https://developer.chrome.com/docs/webstore/program-policies/permissions).

Keep the panel/code bundled with the extension, and fetch analysis JSON from the backend. Manifest V3 prohibits remotely hosted executable code; see [Chrome's migration guidance](https://developer.chrome.com/docs/extensions/develop/migrate/remote-hosted-code). Make service calls from the extension context with appropriate host permissions rather than a page content script; see [cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).

An open panel must show capture provenance and require a new capture after page changes; it must not silently reuse or save a previous product's text. Capture failure, a restricted browser page, lost connection, expired preview, and a restarted panel need explicit recovery states. Store minimal job IDs/settings, and recover durable processing through the API rather than relying on an always-running extension worker.

**Investigate one retailer adapter early; defer universal scraping and “paste any product URL.”** Product matching, complete-review boundaries, pagination/coverage, provenance storage, and access feasibility are the key experiment. First support user-invoked capture of reviews available on the current page; do not promise unattended crawling, login bypass, or all-review coverage. The existing API accepts review text/files, not arbitrary retailer URLs. Choose the initial retailer based on a read-only feasibility check rather than assuming Amazon or another site will work reliably.

## Visual system and responsive behavior

| Element | Proposed treatment |
|---|---|
| Foundation | Preserve the existing Avenir Next/system typography and green/gray tokens; bundled font assets only if a later brand decision requires them |
| Layout | Desktop product navigation around 200–220 px; content uses available width; evidence pane around 340–400 px |
| Type | 28–32 px page titles, 14–16 px reading text, 12–13 px metadata; tabular numerals for counts |
| Surfaces | Mostly flat white areas, subtle dividers, 6–8 px corners; avoid a separate floating card for every statistic |
| Semantics | Positive/neutral/negative text accompanies color; unknown mappings say “Unmapped” |
| Actions | One primary action per step; evidence is a link/button; deletion stays in settings |
| Motion | Short focus/drawer transitions; respect reduced motion; no decorative chart animation |

At 1440 px use the split evidence view. Around 1024 px narrow/collapse navigation. At 768 px stack the evidence area or open a drawer. At 320–390 px show readable feature rows and a full-width evidence view, with counts available as text. Desktop remains the primary annotation surface; compact layouts must still let users read, inspect, and save without horizontal page overflow.

Keyboard access, visible focus, labeled controls, adequate contrast, dialog focus management, and non-color status cues are acceptance requirements. Filters/sort should use URL state where useful. Prototype widths are design targets, not promises that every production screen already meets them.

## Trust and state design

- **No data:** offer paste/import/sample, explain the next step, and avoid empty charts.
- **Too little support:** show detected evidence but withhold recurring product tags until the backend's three-review gate is met.
- **Unknown feature:** retain its source phrase as unmapped; do not invent a canonical tag.
- **Processing:** keep the last published snapshot visible, label it appropriately, and show job progress separately.
- **Failure/disconnection:** preserve user input and recovery IDs; offer the existing retry paths.
- **Model missing:** show a service error. Never silently switch to heuristic output; label heuristic mode whenever explicitly selected.
- **Confidence:** keep raw model scores in evidence details; do not present them as calibrated accuracy or a product rating.
- **Optional assistant unavailable:** show a brief unavailable state; only send excerpts to a provider after an explicit request, with a clear provider disclosure.
- **Reviewer conflict:** preserve the draft, expose the conflict, and reload only deliberately.

## Implementation boundaries

**Reusable now:** analysis/import endpoints, durable jobs, snapshot-based insights, corrections/annotation APIs, two-product comparison, evidence spans, existing primitives and CSS tokens.

**Frontend work:** route composition, product-context navigation, split evidence browser, focused analyze/import screens, responsive behavior, and state presentation. The first version can filter already-returned detail evidence client-side. Server-side evidence search/pagination is a later requirement if product sizes make the current detail response too large.

**New shopping work:** extension manifest/build entry points, one retailer adapter, capture/message handling, absolute API base URL (the web client currently uses relative `/api` URLs), scoped host access, connection setup, and lifecycle recovery. Add explicit product/source identity, capture provenance, source-page links, and an unsaved batch-summary contract. Use the same persisted product IDs in both surfaces. A personal shortlist, authenticated ownership, and account sync are new work; a private local demo can first share its existing product catalog.

**Separate hosting decision:** start with the existing local backend for a private demo. A cloud-backed extension avoids requiring each user to install Python, but adds inference hosting cost, authentication/authorization, isolation, and operational deployment work. Local extension access also needs a tested connection setup; do not assume the web app's Vite proxy works from an extension. Do not expose the current demo API publicly as part of a cosmetic redesign.

## Proposed sequence and approval

| Stage | Deliverable | Review gate |
|---|---|---|
| **1 — recommended first approval** | Prove the shopping flow: unpacked Chrome panel, local service connection, one retailer capture experiment, product/source matching, manual fallback | Confirm complete review boundaries and capture count; verify permissions, source text, product changes, panel restart, and job recovery |
| 2 | Deliver the connected core: bounded multi-review analysis, unsaved batch summary, explicit save, shared saved-product details and two-product comparison | Follow strength/complaint to a quote; verify support gates and sample coverage; open the same persisted product from both surfaces |
| 3 | Polish shopper navigation and compact layouts; keep analysis/import/annotation in Advanced | Verify extension widths and web layouts; preserve draft, import, correction, and export behavior |
| 4 — optional distribution | Hosted service and store release; PWA convenience if useful | Decide deployment/authentication, validate distribution requirements, and test with representative shoppers |

Relative effort: Stage 1 is medium with capture uncertainty; Stage 2 is medium–large because it includes new shared product/provenance and temporary-summary behavior; Stage 3 is medium; Stage 4 varies substantially with hosting and distribution. Calendar estimates should follow the capture experiment.

Suggested formative check: ask representative shoppers to investigate a complaint while browsing, inspect its source, save two candidate products, and compare them on the web. Observe whether they understand capture coverage and whether the extension saves useful reading effort. These are proposed validation tasks, not completed user research.

**Direction captured:** both surfaces, led by the shopping companion. You subsequently authorized edits. The initial extension, temporary summaries, and web evidence/comparison navigation are now described in the [implementation guide](shopping-companion.md). Live retailer feasibility and hosted/store distribution remain open; the original visual board remains an illustrative design artifact.

## Deliverable verification

Before implementation, the revised illustrative board was checked in Chromium at 320, 768, 1024, and 1440 px, including its sample interactions and expanded quotes. Those checks covered only the fixed-output concept board. Current application, extension, and API verification is recorded in the [implementation guide](shopping-companion.md).
