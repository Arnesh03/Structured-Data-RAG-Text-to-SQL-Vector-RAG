"""The FastAPI surface: metadata endpoints, ask, and the SSE stream."""
import json

import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture(scope="module")
def client():
    # Constructed without the context manager on purpose: that skips the
    # lifespan hook, which would rebuild data and warm the embedding model.
    return TestClient(app)


def test_health_reports_every_subsystem(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["database_ready"] and body["vectorstore_ready"]
    assert body["llm_provider"] in {"groq", "openai"}
    assert isinstance(body["has_api_key"], bool)


def test_examples_are_tagged_by_route(client):
    examples = client.get("/api/examples").json()
    assert examples
    assert {e["route"] for e in examples} == {"sql", "rag"}


def test_dashboard_returns_kpis_and_series(client):
    body = client.get("/api/dashboard").json()
    assert body["kpis"]["total_admissions"] > 0
    assert len(body["by_condition"]) == 6


def test_schema_lists_the_admissions_columns(client):
    body = client.get("/api/schema").json()
    assert body["table"] == "admissions"
    assert {c["name"] for c in body["columns"]} >= {"billing_amount", "admission_date"}


def test_documents_list_every_policy_pdf(client):
    docs = client.get("/api/documents").json()
    assert len(docs) == 5
    assert all(d["file"].endswith(".pdf") and d["sections"] for d in docs)


def test_preprocessing_report_is_served(client):
    body = client.get("/api/preprocessing").json()
    assert body["rows_in"] >= body["rows_out"] > 0


def test_empty_question_is_rejected_by_validation(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_ask_returns_a_routed_answer(client, fake_llm):
    fake_llm("sql", "SELECT COUNT(*) AS n FROM admissions", "There are 54,966.")
    body = client.post("/api/ask", json={"question": "How many admissions?"}).json()
    assert body["ok"] and body["route"] == "sql"
    assert body["row_count"] == 1


def _read_events(response) -> list[dict]:
    """Parse an SSE body into the list of decoded events."""
    events = []
    for frame in response.text.split("\n\n"):
        payload = "".join(
            line[5:].strip() for line in frame.splitlines() if line.startswith("data:")
        )
        if payload:
            events.append(json.loads(payload))
    return events


def test_ask_stream_emits_sse_frames(client, fake_llm):
    fake_llm("sql", "SELECT COUNT(*) AS n FROM admissions", "There are 54,966.")
    with client.stream(
        "POST", "/api/ask/stream", json={"question": "How many admissions?"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        response.read()
        events = _read_events(response)

    assert [e["type"] for e in events][0] == "stage"
    assert events[-1]["type"] == "done"
    assert events[-1]["result"]["route"] == "sql"


def test_ask_stream_reports_errors_as_events(client, monkeypatch):
    import pipeline

    def boom(_):
        raise RuntimeError("router exploded")

    monkeypatch.setattr(pipeline, "route_query", boom)
    with client.stream("POST", "/api/ask/stream", json={"question": "hi"}) as response:
        response.read()
        events = _read_events(response)

    assert events[-1]["type"] == "error"
    assert "router exploded" in events[-1]["message"]
