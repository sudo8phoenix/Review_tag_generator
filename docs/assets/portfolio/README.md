# Portfolio screenshot assets

These PNGs capture the actual interface during Playwright verification. They use
synthetic demonstration reviews and generated test product names, not customer data.

| Asset | Caption and provenance |
|---|---|
| [Shopping evidence](shopping-evidence.png) | Current saved-product feature/evidence layout; actual local heuristic backend with synthetic demo reviews, captured at 1440 px during the shopping design pass. |
| [Shopping extension](shopping-extension.png) | Built Manifest V3 extension in isolated real Chromium, actual local heuristic API and synthetic pasted reviews; captured at 390 px by `shopping-companion.spec.ts` before explicit save. |
| [Evidence tools](evidence-tools.png) | Aspect feedback, robustness, quality queue and comparison; real local heuristic pipeline with synthetic review input, captured by `evidence-tools.spec.ts`. |
| [Cited assistant](cited-assistant.png) | Cited Q&A interface; provider responses are explicitly injected in `review-assistant.spec.ts`, so this image demonstrates UI behavior, not a live provider output or model accuracy. |
| [Annotation editor](annotation-editor.png) | Complete-review editor and status controls; real local heuristic API/database with synthetic reviews, captured by `review-annotations.spec.ts`. |
| [Correction drawer](correction-drawer.png) | Saved mapping/sentiment decisions; synthetic reviews and an explicitly injected provider response in `review-corrections.spec.ts`, not live LLM output. |
| [Saved imports](saved-imports.png) | Named review batches and clear/delete controls; real local import workflow with synthetic TXT review input, captured by `saved-data.spec.ts`. |

Use these qualifications in a portfolio caption. The trained pipeline and live
Groq smoke checks are documented separately in the performance and LLM guides.

The first three captures predate the annotation controls and do not show the
entire current product page. The two reviewer captures illustrate the newer
workflows; see [corrections](../../review-corrections.md) and
[annotations](../../review-annotations.md) for current behavior.
