"""Query routing: LLM classification plus the keyword fallback."""
import pytest

import router
from router import RAG_ROUTE, SQL_ROUTE, _keyword_route, _normalize, route_query

SQL_QUESTIONS = [
    "What is the average billing amount by insurance provider?",
    "How many admissions are there for each medical condition?",
    "Which 5 hospitals treated the most cancer patients?",
    "What is the total billing per month in 2023?",
    "How many patients with diabetes were admitted?",
]
RAG_QUESTIONS = [
    "What are the emergency department triage levels?",
    "Who qualifies for financial assistance?",
    "How do I request a copy of my medical records?",
    "What is the policy on advance directives?",
    "Can I change my attending physician?",
]


@pytest.mark.parametrize("question", SQL_QUESTIONS)
def test_keyword_fallback_picks_sql(question):
    assert _keyword_route(question) == SQL_ROUTE


@pytest.mark.parametrize("question", RAG_QUESTIONS)
def test_keyword_fallback_picks_rag(question):
    assert _keyword_route(question) == RAG_ROUTE


@pytest.mark.parametrize("raw,expected", [
    ("sql", SQL_ROUTE),
    ("  RAG.  ", RAG_ROUTE),
    ("Classification: sql", SQL_ROUTE),
    ("I think this is rag", RAG_ROUTE),
    ("banana", None),
])
def test_normalize_extracts_route(raw, expected):
    assert _normalize(raw) == expected


def test_llm_classification_is_used(fake_llm):
    fake_llm("sql")
    assert route_query("anything at all") == SQL_ROUTE


def test_garbage_llm_output_falls_back_to_keywords(fake_llm):
    fake_llm("purple monkey dishwasher")
    assert route_query("What is the visiting hours policy?") == RAG_ROUTE


def test_llm_failure_falls_back_to_keywords(monkeypatch):
    def boom():
        raise RuntimeError("the model provider is down")

    monkeypatch.setattr(router, "get_router", boom)
    assert route_query("What is the average billing amount?") == SQL_ROUTE
    assert route_query("What is the policy on medical records?") == RAG_ROUTE
