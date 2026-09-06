# API reference

FastAPI backend, served by [`server.py`](../server.py) on
`http://127.0.0.1:8010` by default.

Interactive docs while the server is running: **http://127.0.0.1:8010/docs**

```bash
make api
```

---

## Metadata

### `GET /api/health`

Readiness of every moving part, so the UI can explain what is missing rather
than just failing.

```json
{
  "ok": true,
  "llm_provider": "groq",
  "llm_model": "openai/gpt-oss-120b",
  "has_api_key": true,
  "database_ready": true,
  "vectorstore_ready": true
}
```

The frontend disables the composer and shows the reason when `has_api_key` is
false — the dashboard and data views still work without a key.

### `GET /api/examples`

Seed questions for the chat UI, each tagged with the route it should take.

```json
[{ "q": "How many admissions are there for each medical condition?", "route": "sql" }]
```

### `GET /api/schema`

The `admissions` schema, with the comment on each column — the same text the
Text-to-SQL prompt sees.

```json
{
  "table": "admissions",
  "columns": [
    { "name": "admission_id", "type": "TEXT", "description": "e.g. 'ADM-000001'" }
  ]
}
```

### `GET /api/documents`

The policy documents backing the Vector RAG route.

```json
[{ "file": "admission_policy.pdf", "title": "Patient Admission & Triage Policy",
   "sections": ["Purpose and Scope", "Admission Types"] }]
```

### `GET /api/preprocessing`

The cleaning audit trail — `rows_in`, `rows_out`, every step with its counts,
and a summary block. See [DATA.md](DATA.md).

### `GET /api/dashboard`

Every aggregate the analytics view renders, in one round trip. Cached, since
the table is immutable once built.

```json
{
  "kpis": { "total_admissions": 54966, "unique_patients": 48896, "...": "..." },
  "by_condition": [{ "name": "Arthritis", "admissions": 9218, "avg_billing": 25513.05 }],
  "by_month": [], "by_admission_type": [], "by_insurance": [],
  "by_age_group": [], "by_test_result": [], "by_gender": [],
  "by_medication": [], "stay_by_condition": [], "top_hospitals": []
}
```

---

## Question answering

### `POST /api/ask`

Answer a question and return the whole result at once.

```bash
curl -X POST http://127.0.0.1:8010/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the average billing amount by insurance provider?"}'
```

A SQL result:

```json
{
  "question": "...", "route": "sql", "ok": true, "elapsed": 2.6,
  "answer": "The average billing amount is highest for Medicare, at $25,630.16.",
  "sql_query": "SELECT insurance_provider, ROUND(AVG(billing_amount), 2) ... LIMIT 20",
  "columns": ["insurance_provider", "avg_billing"],
  "rows": [["Medicare", 25630.16]],
  "row_count": 5
}
```

A RAG result carries `sources` and `chunks` instead of `sql_query`/`rows`:

```json
{
  "route": "rag", "ok": true,
  "sources": [{ "file": "admission_policy.pdf", "title": "Patient Admission & Triage Policy" }],
  "chunks": [{ "file": "...", "title": "...", "page": 0, "text": "..." }]
}
```

Errors set `ok: false` and put the message in `answer` — a missing API key, an
unsafe query, or an upstream failure. An empty `question` is rejected by
validation with **422**.

### `POST /api/ask/stream`

The same pipeline as server-sent events, one per stage. This is what the web UI
uses.

```bash
curl -N -X POST http://127.0.0.1:8010/api/ask/stream \
  -H 'Content-Type: application/json' \
  -d '{"question": "How many emergency admissions were there in 2023?"}'
```

Each frame is `data: {json}\n\n`.

| `type` | Payload | When |
|---|---|---|
| `stage` | `stage` | Entering a pipeline step |
| `route` | `route`, `label`, `elapsed` | The router has decided |
| `sql` | `sql_query` | SQL generated, **before** it runs |
| `rows` | `columns`, `rows`, `row_count` | Query executed |
| `sources` | `sources`, `chunks` | Retrieval complete |
| `token` | `text` | One chunk of the streamed answer |
| `done` | `result` | Final payload, same shape as `/api/ask` |
| `error` | `message` | Terminal failure |

Stage order is `routing` → (`generating_sql`, `executing_sql` | `retrieving`) →
`answering`.

The stream is why the UI can show the SQL before it runs and the rows before
the prose is written.

---

## Notes

**CORS.** Configured origins plus any `localhost`/`127.0.0.1` port, since the
Next.js dev server picks whatever is free. Credentials are off, so a permissive
dev origin cannot be used to read an authenticated response.

**Startup.** The lifespan hook builds the database and FAISS index if missing
and warms the embedding model, so the first question does not pay for it. First
boot takes a couple of minutes; after that it is a few seconds.

**Threading.** The pipeline is synchronous and LLM-bound. Both endpoints run it
in a worker thread; the streaming one hands events back through an
`asyncio.Queue` rather than blocking the event loop.
