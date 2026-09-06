# Development

Setup, commands, testing, and the things most likely to go wrong.

---

## Requirements

- Python 3.10+
- Node 18+ (only for the Next.js frontend — the CLI and Gradio UI work without it)
- An API key from Groq, DeepSeek or OpenAI

---

## Setup

```bash
make install                                  # venv + Python deps + npm install
echo 'GROQ_API_KEY=gsk_your_key_here' > .env  # free key: console.groq.com/keys
make setup                                    # clean data, build SQLite + FAISS
```

`make setup` takes a couple of minutes the first time — it downloads a ~90 MB
embedding model. Everything after that is local.

---

## Running

Two terminals:

```bash
make api    # FastAPI on http://127.0.0.1:8010
```

```bash
make web    # Next.js on http://localhost:3000
```

Without Node:

```bash
make gradio   # the same pipeline in a Gradio UI, port 7860
make cli      # interactive terminal chat
make demo     # scripted questions across both routes
make stats    # dataset aggregates, no LLM needed
```

`make help` lists every target.

---

## Providers

Three are supported. Change one line in `.env`:

| `LLM_PROVIDER` | Key variable | Notes |
|---|---|---|
| `groq` (default) | `GROQ_API_KEY` | Free tier, fastest |
| `deepseek` | `DEEPSEEK_API_KEY` | Paid, no free tier |
| `openai` | `OPENAI_API_KEY` | Standard OpenAI models |

DeepSeek and OpenAI both speak the OpenAI API and share a client in
[`llm.py`](../llm.py), differing only in base URL. Adding a fourth
OpenAI-compatible provider is a `Provider` entry with a `base_url`.

---

## Configuration

Every value in [`config.py`](../config.py) reads from the environment. See
[`.env.example`](../.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Which provider to use |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chat model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local sentence-transformer |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 600 / 80 | Document splitting |
| `RETRIEVER_TOP_K` | 4 | Passages retrieved per question |
| `SQL_MAX_ROWS` | 20 | Row cap appended to generated SQL |
| `MAX_STAY_DAYS` | 365 | Above this, a stay is treated as a data error |
| `API_PORT` | 8010 | FastAPI port |

The frontend reads `NEXT_PUBLIC_API_URL` from `web/.env.local`, defaulting to
`http://127.0.0.1:8010`.

---

## Testing

```bash
make test
```

**109 tests, all offline.** A scripted `FakeListChatModel` stands in for the
LLM, so no API key is needed and no test costs money.

| File | Covers |
|---|---|
| `test_preprocess.py` | Name normalisation, row-drop rules, derived columns, the audit report |
| `test_database.py` | Schema, row count, indexes, category vocabularies |
| `test_router.py` | LLM classification, keyword fallback, output parsing |
| `test_sql_chain.py` | SQL cleaning, the read-only guard, live execution |
| `test_vectorstore.py` | PDF generation, retrieval relevance per document |
| `test_analytics.py` | Dashboard aggregates, schema view, report |
| `test_pipeline.py` | Dispatch, formatting, streaming event order |
| `test_server.py` | Every endpoint, including the SSE stream |

Frontend checks:

```bash
cd web
npx tsc --noEmit    # types
npx eslint .        # lint
npm run build       # production build
```

---

## Troubleshooting

**`model_not_found` from Groq.** Groq retires models fairly often. Check what
your key can reach at [console.groq.com/docs/models](https://console.groq.com/docs/models)
and set `GROQ_MODEL` in `.env`. The router falls back to keyword matching while
this is broken, so the app stays usable.

**`402 Insufficient Balance` from DeepSeek.** DeepSeek has no free tier. Top up
the account, or switch `LLM_PROVIDER` to `groq`.

**Port already in use.** `API_PORT` moves the backend. For the frontend,
`npm run dev --prefix web -- --port 3001`.

**"API offline" badge in the header.** The backend is not running, or is on a
different port than `NEXT_PUBLIC_API_URL` expects.

**Answers say no API key.** `has_api_key` is false for the *configured*
provider — check that `LLM_PROVIDER` matches the key you actually set.

**Charts or reveals look stuck.** Both were fixed by removing Recharts' entry
animation and adding a timer backstop to the reveal observer. If you reintroduce
either, note that `requestAnimationFrame` does not fire in a renderer that is
not painting.

---

## Rebuilding data

```bash
make rebuild   # everything, from the raw CSV
make clean     # remove generated artifacts and caches
```

`data/` is gitignored in full — it is all reproducible from
`healthcare_dataset.csv`.

---

## Conventions

- Configuration lives in `config.py`, never inline
- Chains are `lru_cache`d; tests clear the caches between cases
- Anything that can fail at the edge of the system degrades rather than raises
- Comments explain *why*, not *what*
