"""
Intelligent Query Router.

Classifies each user query as either:
  - "sql"  -> quantitative questions about the admissions database
              (counts, billing, length of stay, conditions, hospitals)
  - "rag"  -> qualitative questions about hospital policy, clinical guidelines,
              insurance rules, patient rights

An LLM does the classification. If the LLM is unavailable or returns something
unexpected, a keyword heuristic decides instead, so the app still routes
sensibly rather than failing outright.
"""
import re
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm

SQL_ROUTE = "sql"
RAG_ROUTE = "rag"
VALID_ROUTES = (SQL_ROUTE, RAG_ROUTE)

# ── Router Prompt ─────────────────────────────────────────────────────

ROUTER_PROMPT = ChatPromptTemplate.from_template("""\
You are a query router for a hospital analytics assistant. Classify the user's
question into exactly one of two categories:

1. "sql" - The question asks for a number, a count, a ranking, a trend, or a
   record from the patient admissions database. That database holds one row
   per admission with: patient demographics (age, gender, blood type), the
   medical condition recorded at admission, admission and discharge dates,
   length of stay, doctor, hospital, insurance provider, billing amount, room
   number, admission type (Elective/Urgent/Emergency), medication, and test
   result (Normal/Abnormal/Inconclusive).
   Examples: how many patients had diabetes, average billing by insurance
   provider, longest average stay by condition, admissions per month, which
   hospital treated the most cancer patients, share of emergency admissions.

2. "rag" - The question asks about hospital policy, clinical protocol,
   insurance and billing rules, or patient rights, all of which live in policy
   documents rather than the database.
   Examples: what the triage levels mean, whether an elective admission needs
   pre-authorization, the inpatient glucose target, who qualifies for financial
   assistance, how to request medical records, visiting hours, what an
   inconclusive test result means procedurally, discharge criteria.

Rule of thumb: if answering it requires counting or aggregating patient
records, choose sql. If it requires reading a rule, a definition, or a
protocol, choose rag.

Respond with ONLY the word sql or rag. No punctuation, no explanation.

User question: {question}

Classification:""")

# ── Keyword fallback ──────────────────────────────────────────────────

_SQL_KEYWORDS = {
    "average", "avg", "total", "sum", "count", "how many", "number of",
    "top", "most", "least", "highest", "lowest", "trend", "per month",
    "by condition", "by hospital", "by provider", "breakdown", "median",
    "percentage of patients", "share of", "billing amount", "admissions in",
    "patients with", "adm-", "compare", "distribution", "rank",
}

_RAG_KEYWORDS = {
    "policy", "guideline", "protocol", "procedure", "rule", "criteria",
    "eligible", "eligibility", "qualify", "am i allowed", "can i", "how do i",
    "what should i", "visiting hours", "medical records", "hipaa", "privacy",
    "pre-authorization", "preauthorization", "financial assistance",
    "charity care", "advance directive", "complaint", "rights", "consent",
    "triage", "what does it mean", "explain the", "target", "recommended",
}


def _keyword_route(question: str) -> str:
    """Cheap heuristic used when the LLM can't be reached or is ambiguous."""
    text = question.lower()
    sql_hits = sum(1 for kw in _SQL_KEYWORDS if kw in text)
    rag_hits = sum(1 for kw in _RAG_KEYWORDS if kw in text)
    return SQL_ROUTE if sql_hits > rag_hits else RAG_ROUTE


def _normalize(raw: str) -> str | None:
    """Pull a valid route out of a possibly chatty LLM response."""
    tokens = re.findall(r"[a-z]+", raw.lower())
    for token in tokens:
        if token in VALID_ROUTES:
            return token
    return None


@lru_cache(maxsize=1)
def get_router():
    """Build and return the cached query router chain."""
    return ROUTER_PROMPT | get_llm() | StrOutputParser()


def route_query(question: str) -> str:
    """
    Classify a user question as 'sql' or 'rag'.

    Never raises: falls back to the keyword heuristic on any LLM failure.
    """
    try:
        raw = get_router().invoke({"question": question})
    except Exception as exc:  # noqa: BLE001 - routing must not break the chat
        print(f"  Router LLM unavailable ({type(exc).__name__}), using keywords.")
        return _keyword_route(question)

    route = _normalize(raw)
    if route is None:
        print(f"  Router returned {raw!r}; falling back to keywords.")
        return _keyword_route(question)
    return route
