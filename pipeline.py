"""
The end-to-end pipeline: setup, routing, and dispatch.

The API server, the Gradio app, and the CLI all call `answer()`, so there is a
single place where a question becomes a routed, executed, formatted response.
"""
import time

import analytics
from database import database_is_ready, setup_database
from llm import MissingAPIKeyError, has_api_key, model_name, provider
from rag_chain import query_rag
from router import RAG_ROUTE, SQL_ROUTE, route_query
from sql_chain import UnsafeSQLError, query_sql
from vectorstore import load_vectorstore, setup_vectorstore, vectorstore_is_ready

ROUTE_LABELS = {
    SQL_ROUTE: "SQL Database",
    RAG_ROUTE: "Document RAG",
}
ROUTE_ICONS = {
    SQL_ROUTE: "🗄️",
    RAG_ROUTE: "📄",
}

EXAMPLE_QUESTIONS = [
    # Text-to-SQL route
    {"q": "How many admissions are there for each medical condition?", "route": "sql"},
    {"q": "What is the average billing amount by insurance provider?", "route": "sql"},
    {"q": "Which medical condition has the longest average length of stay?", "route": "sql"},
    {"q": "How many emergency admissions were there in 2023?", "route": "sql"},
    {"q": "What share of admissions had abnormal test results?", "route": "sql"},
    {"q": "Show total billing per month in 2023.", "route": "sql"},
    {"q": "Which 5 hospitals treated the most cancer patients?", "route": "sql"},
    {"q": "What is the average age of patients admitted for diabetes?", "route": "sql"},
    # Vector RAG route
    {"q": "What do the emergency department triage levels mean?", "route": "rag"},
    {"q": "Does an elective admission need pre-authorization?", "route": "rag"},
    {"q": "What is the inpatient blood glucose target for diabetic patients?", "route": "rag"},
    {"q": "Who qualifies for financial assistance or charity care?", "route": "rag"},
    {"q": "How do I request a copy of my medical records?", "route": "rag"},
    {"q": "What are the criteria for discharging a patient?", "route": "rag"},
    {"q": "What happens if a neutropenic cancer patient develops a fever?", "route": "rag"},
    {"q": "What are the visiting hours?", "route": "rag"},
]


def initialize(warm: bool = True, force: bool = False) -> None:
    """Build the database and vector store if needed, then warm the index."""
    print("Initializing Healthcare Structured Data RAG...")

    if force or not database_is_ready():
        setup_database(force=force)
    else:
        print("  Database ready.")

    if force or not vectorstore_is_ready():
        setup_vectorstore(force=force)
    else:
        print("  Vector store ready.")

    if force:
        # The dashboard aggregates are cached against the old table otherwise.
        analytics.clear_caches()

    if warm:
        # Loading the embedding model takes a few seconds; do it now rather
        # than inside the user's first question.
        print("  Warming embedding model...")
        load_vectorstore()

    if not has_api_key():
        key = "GROQ_API_KEY" if provider() == "groq" else "OPENAI_API_KEY"
        url = ("https://console.groq.com/keys" if provider() == "groq"
               else "https://platform.openai.com/api-keys")
        print(
            f"\n  WARNING: {key} is not set - the app will start, but "
            "answering questions needs a key.\n"
            f"  Get one at {url} and put it in .env"
        )

    print(f"System ready ({provider()} / {model_name()}).\n")


def answer(question: str) -> dict:
    """
    Route a question and run the matching pipeline.

    Always returns a dict with at least: 'question', 'route', 'answer', 'ok',
    'elapsed'. SQL results add 'sql_query'/'columns'/'rows'; RAG results add
    'sources'/'chunks'. Errors set ok=False and put the message in 'answer'.
    """
    started = time.perf_counter()
    question = (question or "").strip()

    if not question:
        return {
            "question": question,
            "route": None,
            "answer": "Please enter a question.",
            "ok": False,
            "elapsed": 0.0,
        }

    try:
        route = route_query(question)
        routed_at = time.perf_counter()
        result = query_sql(question) if route == SQL_ROUTE else query_rag(question)
        result.update(question=question, ok=True,
                      route_elapsed=routed_at - started)
    except MissingAPIKeyError as exc:
        result = {"question": question, "route": None, "answer": str(exc), "ok": False}
    except UnsafeSQLError as exc:
        result = {
            "question": question,
            "route": SQL_ROUTE,
            "answer": f"I couldn't build a safe query for that question: {exc}",
            "ok": False,
        }
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        result = {
            "question": question,
            "route": None,
            "answer": f"{type(exc).__name__}: {exc}",
            "ok": False,
        }

    result["elapsed"] = time.perf_counter() - started
    return result


def format_response(result: dict) -> str:
    """Render a pipeline result as markdown, for the chat UIs that want text."""
    route = result.get("route")

    if not result.get("ok"):
        return f"❌ **Error**\n\n{result['answer']}"

    icon = ROUTE_ICONS.get(route, "❓")
    label = ROUTE_LABELS.get(route, "Unknown")
    header = f"{icon} **Routed to: {label}**  ·  *{result['elapsed']:.1f}s*"

    if route == SQL_ROUTE:
        detail = f"*Generated SQL:*\n```sql\n{result.get('sql_query', 'N/A')}\n```"
    else:
        titles = [s["title"] for s in result.get("sources") or []]
        detail = f"*Sources: {', '.join(titles) if titles else 'N/A'}*"

    return f"{header}\n\n{result['answer']}\n\n---\n{detail}"


# ═══════════════════════════════════════════════════════════════════════
# Streaming
# ═══════════════════════════════════════════════════════════════════════
#
# The chat UI shows the pipeline working rather than a spinner: which route
# was chosen, the SQL before it runs, the rows it returned, then the answer
# token by token. `answer_events` yields those steps in order.

def _sql_events(question: str):
    """Yield the Text-to-SQL stages, then the streamed answer."""
    from sql_chain import generate_sql, get_answer_chain, rows_as_text, run_query

    yield {"type": "stage", "stage": "generating_sql"}
    sql_query = generate_sql(question)
    yield {"type": "sql", "sql_query": sql_query}

    yield {"type": "stage", "stage": "executing_sql"}
    columns, rows = run_query(sql_query)
    yield {"type": "rows", "columns": columns, "rows": rows, "row_count": len(rows)}

    yield {"type": "stage", "stage": "answering"}
    text = ""
    for chunk in get_answer_chain().stream({
        "question": question,
        "query": sql_query,
        "result": rows_as_text(columns, rows),
    }):
        text += chunk
        yield {"type": "token", "text": chunk}

    yield {"type": "result", "result": {
        "answer": text, "sql_query": sql_query, "columns": columns,
        "rows": rows, "row_count": len(rows), "route": SQL_ROUTE,
    }}


def _rag_events(question: str):
    """Yield the Vector RAG stages, then the streamed answer."""
    from rag_chain import NO_ANSWER, format_docs, get_answer_chain, get_retriever
    from vectorstore import SOURCE_TITLES

    yield {"type": "stage", "stage": "retrieving"}
    docs = get_retriever().invoke(question)

    if not docs:
        yield {"type": "token", "text": NO_ANSWER}
        yield {"type": "result", "result": {
            "answer": NO_ANSWER, "sources": [], "chunks": [], "route": RAG_ROUTE,
        }}
        return

    sources, seen, chunks = [], set(), []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown")
        title = doc.metadata.get("title", SOURCE_TITLES.get(source, source))
        if source not in seen:
            seen.add(source)
            sources.append({"file": source, "title": title})
        chunks.append({
            "file": source, "title": title,
            "page": doc.metadata.get("page"),
            "text": doc.page_content.strip(),
        })
    yield {"type": "sources", "sources": sources, "chunks": chunks}

    yield {"type": "stage", "stage": "answering"}
    text = ""
    for chunk in get_answer_chain().stream({
        "context": format_docs(docs),
        "question": question,
        "no_answer": NO_ANSWER,
    }):
        text += chunk
        yield {"type": "token", "text": chunk}

    yield {"type": "result", "result": {
        "answer": text, "sources": sources, "chunks": chunks, "route": RAG_ROUTE,
    }}


def answer_events(question: str):
    """
    Run a question and yield the pipeline's progress as it happens.

    The final event is always either `{"type": "done", ...}` with the same
    payload `answer()` would have returned, or `{"type": "error", ...}`.
    """
    started = time.perf_counter()
    question = (question or "").strip()

    if not question:
        yield {"type": "error", "message": "Please enter a question."}
        return

    result: dict = {}
    try:
        yield {"type": "stage", "stage": "routing"}
        route = route_query(question)
        yield {"type": "route", "route": route,
               "label": ROUTE_LABELS.get(route, "Unknown"),
               "elapsed": time.perf_counter() - started}

        events = _sql_events(question) if route == SQL_ROUTE else _rag_events(question)
        for event in events:
            if event["type"] == "result":
                result = event["result"]
            else:
                yield event
    except MissingAPIKeyError as exc:
        yield {"type": "error", "message": str(exc)}
        return
    except UnsafeSQLError as exc:
        yield {"type": "error",
               "message": f"I couldn't build a safe query for that question: {exc}"}
        return
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
        return

    result.update(question=question, ok=True, elapsed=time.perf_counter() - started)
    yield {"type": "done", "result": result}
