# Chrome shopping companion

Manifest V3 side panel, version **0.1.1**, requiring **Chrome 116+**.
The source is included in this GitHub repository. The compiled `frontend/dist-extension/`
directory is generated locally and intentionally ignored by Git. Installation here
uses Chrome's **Load unpacked** workflow; a Chrome Web Store installation is not
part of this guide.

## Build and install

Clone or download the repository from
[GitHub](https://github.com/sudo8phoenix/Review_tag_generator), then run from its root
with Node.js **22** and npm:

```bash
npm --prefix frontend ci
npm --prefix frontend run build:extension
```

1. Open `chrome://extensions` and enable **Developer mode**.
2. Select **Load unpacked** and choose `frontend/dist-extension` (the directory
   containing the generated `manifest.json`, not this source directory).
3. Pin the extension, open a shopping webpage, and click its toolbar icon.
4. Check **Connection settings**. New installs use
   `https://review-tag-generator.vercel.app`; saved settings survive upgrades.
5. Paste reviews separated by blank lines, capture selected text, or try loaded
   reviews on Amazon.com/.in, Flipkart, Walmart, Best Buy, or Target.
6. Choose or explicitly create a product. Preview to inspect feedback, or choose
   **Save captured reviews** to store and queue analysis immediately. Downloading
   the captured TXT file does not contact the API.
7. Wait for Save progress to finish, then open the product in the web workspace.

The hosted service can take time to wake. It shares saved data and has no personal
account isolation. Use local mode for private reviews. The hosted path needs no
local Python environment or model downloads. Free-hosting limits and optional AI
availability are described in [Render demo](../../docs/render-demo.md).

## Local connection

Follow [getting started](../../docs/getting-started.md) to install Python dependencies,
retrieve model checkpoints, and start the API and web app. In Connection settings,
select **Localhost (127.0.0.1)**, API port **8000**, and workspace port **5173**.
Match alternate ports to your servers; the web development proxy does not configure
the extension's API connection. Hosted mode accepts Vercel/Render HTTPS origins;
use an origin without an `/api` suffix, path, query, or fragment.

## Source map

| Location (from repository root) | Purpose |
|---|---|
| `frontend/extension/public/manifest.json` | Version, permissions, CSP, side-panel configuration |
| `frontend/extension/public/service-worker.js` | Toolbar action opens the side panel |
| `frontend/extension/sidepanel.html` | Bundled panel entry |
| `frontend/src/extension/` | React panel, capture adapters, styles, API client, unit checks |
| `frontend/vite.extension.config.ts` | Dedicated Vite build into `frontend/dist-extension/` |
| `frontend/e2e/` | Browser integration and hosted-demo checks |

## Permissions and data

The manifest requests `sidePanel`, `activeTab`, `scripting`, and `storage`.
Service host permissions and CSP allow loopback HTTP and Vercel/Render HTTPS.
Explicit retailer host permissions allow user-invoked loaded-review capture on
the listed retailers. Other sites need a toolbar invocation before selected-text
capture. Capture reads loaded review content; it does not crawl or paginate.
Retailer layouts remain experimental; selection and paste are fallbacks.

Each batch accepts up to **100 reviews**, each up to **10,000 Unicode code points**.
Preview sends text to the configured backend and creates temporary preview records;
it does not add saved review totals. Saving persists text and a processing job.
Chrome local storage retains connection settings and one pending save with its
review text, destination, and recovery identifiers. Completed jobs remove the
recovery record. Other captures and previews remain in panel memory. Inference
runs on the backend; model weights are not bundled into the extension.

## Updates and troubleshooting

After updating source, rebuild, click **Reload** in `chrome://extensions`, and
close/reopen the side panel. Allow site access if Chrome prompts. Existing
connection settings are retained, so select hosted mode explicitly when switching
from an older local setup.

| Symptom | Action |
|---|---|
| Missing manifest when loading | Build first; select `frontend/dist-extension` |
| Old behavior or CSP errors | Reload the extension and reopen its panel; inspect new errors |
| API disconnected | Check the connection origin/ports; allow hosted backend wake-up time |
| No reviews captured | Expand/load review bodies, then try selection or paste |
| Save still processing | Inspect progress; recovery resumes after reopening the panel |
| Some rows failed | Inspect row-error CSV and retry failed reviews |
| Recovered job was deleted | Use **Clear missing job recovery** to release the stale browser record |

For validation commands see [verification](../../docs/verification.md). Build before
running extension browser tests. Recorded integration evidence and detailed
behavior are in [shopping companion](../../docs/shopping-companion.md); documentation
updates do not imply a new run of the browser or model suites.
