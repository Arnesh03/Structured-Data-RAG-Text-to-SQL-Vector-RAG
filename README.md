# 🏥 Healthcare Structured Data RAG

**A hybrid RAG system with an intelligent query router**, built on 55,500 hospital
admission records. One chat interface answers both *"which condition has the longest
average stay?"* and *"who qualifies for financial assistance?"* — because a router
decides which of two very different pipelines should handle each question.

```
                        ┌─────────────────────────────────────┐
                        │        LLM Query Router             │
   User question  ───►  │  quantitative? ──► sql              │
                        │  qualitative?  ──► rag              │
                        └──────────┬──────────────┬───────────┘
                                   │              │
                    ┌──────────────▼───┐     ┌────▼─────────────────┐
                    │  Text-to-SQL     │     │  Vector RAG          │
                    │  SQLite          │     │  FAISS + MiniLM      │
                    │  54,966 rows     │     │  5 policy PDFs       │
                    └──────────────┬───┘     └────┬─────────────────┘
                                   │              │
                                   └──────┬───────┘
                                          ▼
                          grounded answer + the SQL that ran
                          or the passages that were retrieved
```

The router never sees the data. It sees the question, picks a lane, and the chosen
pipeline does the rest — so a question about *billing amounts* becomes a `GROUP BY`,
and a question about *the billing policy* becomes a vector search.

---

## What's in the box

| Layer | What it does |
|---|---|
| **Preprocessing** (`preprocess.py`) | Cleans the raw Kaggle CSV: normalizes scrambled-case names, tidies hospital names, drops duplicate and impossible rows, repairs negative charges, derives length of stay / age group / billing per day. Writes an auditable JSON report of every change. |
| **Database** (`database.py`) | Loads the clean frame into a single wide, commented `admissions` table with eight indexes. |
| **Documents** (`vectorstore.py`) | Renders five hospital policy documents to PDF, chunks them, embeds them locally with `all-MiniLM-L6-v2`, and indexes them in FAISS. |
| **Router** (`router.py`) | LLM classifier with a keyword-heuristic fallback, so routing degrades instead of failing. |
| **Text-to-SQL** (`sql_chain.py`) | Generates SQL, validates it is a single read-only statement, executes it on a read-only connection, and turns the rows back into prose. |
| **Vector RAG** (`rag_chain.py`) | Retrieves the top-k passages and answers strictly from them, refusing when the context doesn't cover the question. |
| **API** (`server.py`) | FastAPI. Answers stream back as server-sent events, one per pipeline stage. |
| **Frontend** (`web/`) | Next.js 16 · React 19 · Tailwind v4 · Recharts. Streaming chat, an analytics dashboard, the cleaning audit trail, and the document corpus. |

---

## Documentation

| | |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | How a question becomes an answer: the router, both pipelines, the safety model, streaming |
| [Data](docs/DATA.md) | The dataset, every cleaning step, the schema, the document corpus |
| [API](docs/API.md) | Endpoint reference, payload shapes, the SSE event protocol |
| [Development](docs/DEVELOPMENT.md) | Setup, commands, configuration, testing, troubleshooting |

---

## The dataset

`healthcare_dataset.csv` — 55,500 synthetic hospital admissions, 15 columns.
It is deliberately messy, which is the point of the preprocessing step:

| Problem in the raw file | What preprocessing does |
|---|---|
| `Bobby JacksOn`, `LesLie TErRy` — scrambled case | Title-cases 55,467 names, preserving `O'Brien`, `Smith-Jones`, `McDonald`, `de la Cruz` |
| `Hernandez Rogers and Vang,` — trailing commas, dangling conjunctions | Tidies 13,519 hospital names |
| 534 byte-identical rows | Dropped as duplicate admissions |
| 106 negative billing amounts | Treated as sign errors; magnitude kept, rounded to cents |
| `18856.281305978155` | Rounded to 2 decimals |
| No patient key, no stay length, no age band | Derives `patient_id`, `length_of_stay_days`, `age_group`, `admission_month`, `billing_per_day` and three more |

**55,500 rows in → 54,966 rows out (99.0% retained), 15 columns → 23.**
The full audit trail lives in `data/preprocessing_report.json` and is rendered in
the app's **Data** tab. Every step is documented in [docs/DATA.md](docs/DATA.md).

### The document corpus

The RAG side answers from five documents covering what the table can't:

- **Patient Admission & Triage Policy** — admission types, ED triage levels, pre-admission testing, room assignment, observation status
- **Insurance, Billing & Financial Assistance Policy** — the five providers, pre-authorization, billing timelines, charity care, surprise-billing protections
- **Clinical Care Guidelines** — inpatient protocols for all six conditions in the data, the five formulary medications, and what a test result means
- **Discharge, Follow-Up & Readmission Policy** — discharge criteria, medication reconciliation, follow-up windows, readmission review
- **Patient Rights & FAQ** — visiting hours, medical records, HIPAA, advance directives, interpretation

---

## Quick start

```bash
make install                                  # venv + Python deps + npm install
echo 'GROQ_API_KEY=gsk_your_key_here' > .env  # free key: console.groq.com/keys
make setup                                    # clean data, build SQLite + FAISS
```

The default chat model is `openai/gpt-oss-120b` on Groq. Groq retires models
fairly often, so if a request comes back `model_not_found`, check what your key
can reach at [console.groq.com/docs/models](https://console.groq.com/docs/models)
and set `GROQ_MODEL` in `.env`.

Then run the two servers in separate terminals:

```bash
make api    # FastAPI on http://127.0.0.1:8010
```

```bash
make web    # Next.js on http://localhost:3000
```

`make setup` takes a couple of minutes the first time — it downloads a ~90 MB
embedding model. Everything after that is local and instant.

### Without Node

```bash
make gradio   # the same pipeline in a Gradio chat UI, port 7860
make cli      # interactive terminal chat
make demo     # scripted questions across both routes
make stats    # dataset aggregates, no LLM needed
```

### Switching providers

Three providers are supported; change one line in `.env`:

| `LLM_PROVIDER` | Key | Notes |
|---|---|---|
| `groq` (default) | `GROQ_API_KEY` | Free tier, fastest. Retires models often — see below. |
| `deepseek` | `DEEPSEEK_API_KEY` | Paid, no free tier; an empty balance returns `402 Insufficient Balance`. |
| `openai` | `OPENAI_API_KEY` | Standard OpenAI models. |

DeepSeek and OpenAI both speak the OpenAI API and share a client in
[`llm.py`](llm.py), differing only in base URL. Nothing outside that module
knows which provider is in use.

---

## Try it

**Text-to-SQL route**
- How many admissions are there for each medical condition?
- What is the average billing amount by insurance provider?
- Which medical condition has the longest average length of stay?
- How many emergency admissions were there in 2023?
- What share of admissions had abnormal test results?
- Which 5 hospitals treated the most cancer patients?

**Vector RAG route**
- What do the emergency department triage levels mean?
- Does an elective admission need pre-authorization?
- What is the inpatient blood glucose target for diabetic patients?
- Who qualifies for financial assistance or charity care?
- What happens if a neutropenic cancer patient develops a fever?
- How do I request a copy of my medical records?

---

## The interface

Four tabs, one backend:

- **Ask** — streaming chat. Each answer shows the route it took, the pipeline
  stages as they run, and its evidence: the generated SQL with a live result
  table (switchable to a chart), or the retrieved passages with their source
  documents.
- **Dashboard** — KPIs and nine charts computed in SQL: admissions over time,
  condition mix, admission types, insurer billing, age bands, test results,
  length of stay.
- **Data** — the cleaning pipeline as an audit trail, step by step with counts,
  next to the table schema the SQL prompt actually sees.
- **Documents** — the policy corpus behind the RAG route.

Light and dark themes, keyboard-driven composer, and every panel keeps its state
across tab switches.

---

## Safety and guardrails

The SQL path is the sharp edge, so it is fenced in three places:

1. **Prompt** — the model is told to emit one read-only `SELECT`.
2. **Validation** — `validate_sql()` rejects multiple statements, anything that
   isn't `SELECT`/`WITH`, and any DDL/DML keyword. `enforce_limit()` caps rows.
3. **Connection** — queries execute over `file:...?mode=ro`, so even a query that
   slipped past validation cannot write.

The RAG path answers only from retrieved context and returns a fixed refusal when
the documents don't cover the question. Both answer prompts state that these are
historical records and institutional policies, not medical advice.

Routing itself never hard-fails: if the LLM is unreachable or returns something
unparseable, a keyword heuristic decides.

The full reasoning is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Testing

```bash
make test
```

109 tests, all offline — a scripted `FakeListChatModel` stands in for the LLM, so
no API key is needed. Coverage spans name normalization and the row-drop rules,
the SQLite schema and its category vocabularies, SQL cleaning and the read-only
guard, retrieval relevance per document, the dashboard aggregations, the streaming
event order for both routes, and every API endpoint including the SSE stream.

---

## Project layout

```
config.py             every tunable, env-overridable
llm.py                provider factory (Groq | OpenAI), cached
preprocess.py         raw CSV -> clean frame + audit report
database.py           clean frame -> SQLite
policies_content.py   the policy corpus, as text
vectorstore.py        corpus -> PDFs -> chunks -> FAISS
router.py             question -> "sql" | "rag"
sql_chain.py          Text-to-SQL, validated and executed read-only
rag_chain.py          retrieve -> answer strictly from context
analytics.py          dashboard aggregations, pure SQL
pipeline.py           initialize / answer / answer_events
server.py             FastAPI + SSE
app.py                Gradio fallback UI
cli.py                terminal interface
tests/                109 offline tests
web/                  Next.js 16 frontend
```

---

## Stack

Python · LangChain · SQLite · FAISS · sentence-transformers · Groq (or OpenAI) ·
FastAPI · pandas · Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · Recharts

---

> The dataset is synthetic and used for demonstration only. Nothing here is
> medical advice, and no real patient data is involved.
