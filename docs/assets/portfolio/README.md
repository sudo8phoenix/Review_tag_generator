# Portfolio screenshot assets

These PNGs capture the actual interface during Playwright verification. They use
synthetic demonstration reviews and generated test product names, not customer data.

| Asset | Caption and provenance |
|---|---|
| [Evidence tools](evidence-tools.png) | Aspect feedback, robustness, quality queue and comparison; real local heuristic pipeline with synthetic review input, captured by `evidence-tools.spec.ts`. |
| [Cited assistant](cited-assistant.png) | Cited Q&A interface; provider responses are explicitly injected in `review-assistant.spec.ts`, so this image demonstrates UI behavior, not a live provider output or model accuracy. |
| [Saved imports](saved-imports.png) | Named review batches and clear/delete controls; real local import workflow with synthetic TXT review input, captured by `saved-data.spec.ts`. |

Use these qualifications in a portfolio caption. The trained pipeline and live
Groq smoke checks are documented separately in the performance and LLM guides.
