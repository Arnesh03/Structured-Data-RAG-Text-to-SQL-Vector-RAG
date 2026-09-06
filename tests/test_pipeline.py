"""End-to-end dispatch, response formatting, and the streaming event feed."""
import pipeline
from llm import MissingAPIKeyError
from pipeline import EXAMPLE_QUESTIONS, answer, answer_events, format_response


def test_blank_question_is_rejected():
    result = answer("   ")
    assert result["ok"] is False
    assert "enter a question" in result["answer"].lower()


def test_sql_route_dispatches_to_sql_chain(monkeypatch):
    monkeypatch.setattr(pipeline, "route_query", lambda q: "sql")
    monkeypatch.setattr(
        pipeline, "query_sql",
        lambda q: {"answer": "$25,546.24", "sql_query": "SELECT 1", "route": "sql"},
    )
    result = answer("What is the average billing amount?")
    assert result["ok"] and result["route"] == "sql"
    assert result["sql_query"] == "SELECT 1"
    assert result["elapsed"] >= 0


def test_rag_route_dispatches_to_rag_chain(monkeypatch):
    monkeypatch.setattr(pipeline, "route_query", lambda q: "rag")
    monkeypatch.setattr(
        pipeline, "query_rag",
        lambda q: {
            "answer": "Within 10 minutes.",
            "sources": [{"file": "admission_policy.pdf", "title": "Admission Policy"}],
            "route": "rag",
        },
    )
    result = answer("How fast is triage?")
    assert result["ok"] and result["route"] == "rag"
    assert result["sources"][0]["file"] == "admission_policy.pdf"


def test_missing_api_key_is_reported_not_raised(monkeypatch):
    def boom(_):
        raise MissingAPIKeyError("GROQ_API_KEY is not set.")

    monkeypatch.setattr(pipeline, "route_query", boom)
    result = answer("anything")
    assert result["ok"] is False
    assert "GROQ_API_KEY" in result["answer"]


def test_unexpected_errors_are_caught(monkeypatch):
    def boom(_):
        raise ValueError("kaboom")

    monkeypatch.setattr(pipeline, "route_query", boom)
    result = answer("anything")
    assert result["ok"] is False
    assert "kaboom" in result["answer"]


def test_format_response_shows_sql_and_route():
    text = format_response({
        "ok": True, "route": "sql", "answer": "$25,546.24",
        "sql_query": "SELECT AVG(billing_amount) FROM admissions", "elapsed": 1.2,
    })
    assert "SQL Database" in text
    assert "```sql" in text
    assert "SELECT AVG(billing_amount) FROM admissions" in text


def test_format_response_shows_source_titles():
    text = format_response({
        "ok": True, "route": "rag", "answer": "Within 10 minutes.",
        "sources": [
            {"file": "admission_policy.pdf", "title": "Admission Policy"},
            {"file": "patient_faq.pdf", "title": "Patient FAQ"},
        ],
        "elapsed": 0.8,
    })
    assert "Document RAG" in text
    assert "Admission Policy, Patient FAQ" in text


def test_format_response_renders_errors():
    text = format_response({"ok": False, "route": None, "answer": "boom", "elapsed": 0.0})
    assert text.startswith("❌")
    assert "boom" in text


def test_every_example_question_is_tagged_with_a_valid_route():
    assert EXAMPLE_QUESTIONS
    assert all(ex["route"] in {"sql", "rag"} for ex in EXAMPLE_QUESTIONS)
    assert all(ex["q"].strip() for ex in EXAMPLE_QUESTIONS)


# ── Streaming ─────────────────────────────────────────────────────────

def _collect(question: str) -> list[dict]:
    return list(answer_events(question))


def test_blank_question_streams_a_single_error():
    events = _collect("  ")
    assert [e["type"] for e in events] == ["error"]


def test_sql_stream_reports_every_stage_in_order(fake_llm):
    fake_llm(
        "sql",
        "SELECT COUNT(*) AS n FROM admissions",
        "There are 54,966 admissions.",
    )
    events = _collect("How many admissions are there?")
    stages = [e["stage"] for e in events if e["type"] == "stage"]
    assert stages == ["routing", "generating_sql", "executing_sql", "answering"]

    types = [e["type"] for e in events]
    assert types[0] == "stage" and types[-1] == "done"
    assert "route" in types and "sql" in types and "rows" in types and "token" in types

    done = events[-1]["result"]
    assert done["ok"] and done["route"] == "sql"
    assert done["columns"] == ["n"] and done["row_count"] == 1
    assert done["answer"] == "".join(e["text"] for e in events if e["type"] == "token")


def test_rag_stream_reports_sources_before_the_answer(fake_llm):
    fake_llm("rag", "Level 1 patients are seen immediately.")
    events = _collect("What are the triage levels?")
    stages = [e["stage"] for e in events if e["type"] == "stage"]
    assert stages == ["routing", "retrieving", "answering"]

    types = [e["type"] for e in events]
    assert types.index("sources") < types.index("token")

    done = events[-1]["result"]
    assert done["ok"] and done["route"] == "rag"
    assert done["sources"] and done["chunks"]


def test_stream_surfaces_unsafe_sql_as_an_error(fake_llm):
    fake_llm("sql", "DROP TABLE admissions")
    events = _collect("delete everything")
    assert events[-1]["type"] == "error"
    assert "safe query" in events[-1]["message"]
