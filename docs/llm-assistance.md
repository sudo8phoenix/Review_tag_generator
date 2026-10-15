# Optional LLM assistance

The trained extraction/sentiment pipeline stays reproducible and works without an
LLM. Two user-triggered assistance features run beside it:

1. **Unknown-aspect suggestions:** open an unknown aspect's evidence drawer and
   select **Suggest mapping**. The assistant may suggest an existing canonical
   feature, propose a new feature label, or abstain.
2. **Ask about these reviews:** ask a question on a product insights page. The
   service retrieves relevant saved review excerpts and asks for a cited answer.

Suggestions and answers are ephemeral. They do not change saved analyses,
normalization mappings, tags, model scores, or aggregate totals. A proposed new
feature is not automatically added to the ontology or used in training.

## Why high-scoring aspects can remain unknown

The model score summarizes extraction and sentiment confidence, not normalization
coverage. The current 21-feature ontology deliberately excludes some concepts.
For example, an assistant might map “speed” to Performance, propose Operating
System for “Windows 11”, and abstain on the overly broad word “computer”. These
are examples of possible reasoning, not guaranteed model outputs.

## Configure Groq

Create a server-only `.env.llm` file at the project root:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=your-key-here
```

The demo startup script loads this ignored file. Restart the app after changing
it. The key is sent only as an authorization header to Groq; it is not included in
browser configuration, status responses, prompts, or Git. The model must support
strict JSON-schema output. The initial configured model is `openai/gpt-oss-20b`.

For the manually launched API, load the same file into its environment before
starting Uvicorn:

```bash
set -a
. ./.env.llm
set +a
DEMO_DATABASE=.demo/showcase.sqlite3 .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011
```

The showcase frontend uses `API_PROXY_TARGET=http://127.0.0.1:8011` when started.
The usual `./scripts/start_demo.sh` uses API port 8000 and frontend port 5173.
Compose uses `.env.release`; supply the same LLM settings there if deploying.

## Other supported connections

Gemini:

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=gemini-flash-latest
GEMINI_API_KEY=your-key-here
```

Local Ollama, using a model you have already installed:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Start Ollama yourself with `ollama serve`. The app never downloads a model or
silently switches providers. Cloud providers receive review text only when a user
requests assistance. The UI identifies the configured provider before submission.
Use `LLM_PROVIDER=disabled` to turn assistance off. `LLM_TIMEOUT_SECONDS` defaults
to 90 and must be finite and between 1 and 120.

## Grounding and validation

Normalization includes the exact aspect phrase, Unicode code-point offsets,
review text, and the current ontology. Only ontology IDs are accepted as canonical
mappings; invalid IDs reject the response. Proposed labels remain suggestions.
The API validates offsets against the submitted original text before generation.

Question answering uses deterministic lexical retrieval with canonical-aspect
alias expansion. It considers only the published snapshot's reviews, retrieves
at most eight reviews, and bounds excerpt text to 18,000 characters. It does not
browse the web, search other products, or answer from a provider's general product
knowledge. No matching evidence produces an explicit insufficient-evidence result
without calling the LLM.

Generated answers allow at most six claims. Each claim needs citations, and every
citation's review ID and exact quote must match the retrieved source. Invalid
citations reject the whole response. The browser also checks snapshot identity
before showing an answer, so concurrent imports cannot silently mix evidence.

These checks prove the cited text exists, not that the generated interpretation
is correct. The UI presents quotes so people can inspect whether they support the
claim. Scores from these features are not added to the recorded ML evaluations.
Review text and questions are framed as untrusted data in prompts; the assistant
has no tools, write access, or instructions to execute content from reviews.

Only one generation runs at a time per API process. Extra concurrent calls return
429. Providers are time-bounded, responses are size-bounded, and invalid or
incomplete JSON fails cleanly. There is no automatic retry that could make repeated
paid requests. Provider 503, quota, and credential errors are reported without
returning raw provider bodies or secrets. Configured status does not guarantee
that the provider is currently healthy.

## API

| Route | Purpose |
|---|---|
| `GET /api/assist/status` | Configuration status, provider and model; never a key |
| `POST /api/assist/normalize` | Exact-span suggestion from review text and offsets |
| `POST /api/demo/products/{id}/ask` | Question answering from published reviews |

The suggestion body is `{review_text, raw_aspect, start_char, end_char}`. The
question body is `{question}` with a nonblank maximum of 500 characters.
Suggestions return canonical/proposed labels, explanation, source span, provider,
model and `applied=false`. Answers return claims, citations, retrieval count and
snapshot provenance. HTTP 422 means invalid input, 429 means this process is busy,
502 means generated evidence failed validation, and 503 means the configured
provider is missing or unavailable. Provider rate/quota failures currently map to
503 with a specific retry/check-quota message.

## Verification and limitations

Unit and HTTP tests inject generation responses explicitly; they do not make paid
requests or require API keys. Browser tests inject provider responses only inside
the test harness to check controls, citation rendering, source span rendering and
disabled configuration. These checks do not establish model suggestion accuracy.

A live Gemini request during implementation returned HTTP 503 with a high-demand
message. The configured Groq connection subsequently passed live smoke checks for mapping
“speed” to Performance and answering a battery question with exact quotes from
two synthetic reviews. These checks verify connectivity and citation handling,
not suggestion accuracy on a representative dataset. Unit tests remain injected
and do not themselves establish live cloud inference.

Provider request formats were checked against the official documentation:
[Groq structured outputs](https://console.groq.com/docs/structured-outputs),
[Gemini generateContent](https://ai.google.dev/api/generate-content), and
[Ollama chat](https://docs.ollama.com/api/chat).


The HTTP client identifies itself with `User-Agent: ReviewTagGenerator/0.1`.
Groq initially returned HTTP 403 / edge error 1010 for the default Python client;
the explicit application identity resolved that rejection in the live check.
