"""
HTTP surface over the trace store, for the Evals tab in the web UI.

Recorded results are strictly read-only. Everything under /summary, /runs and
/dataset is a projection of what `evalkit.store` already holds: a dashboard
that could re-score a past run would be a dashboard whose numbers you could
not trust.

Two endpoints do write, and neither touches a recorded run:

  POST /try         runs ONE ad-hoc question through the pipeline and grades
                    what it can. Nothing is stored; it is a scratchpad.
  POST /candidates  appends a question to candidates.jsonl with reviewed:false,
                    so it still has to pass `make eval-promote` to reach the
                    golden set.

The whole router degrades to `has_data: false` when no run has been recorded
yet, so the UI can explain how to produce one instead of rendering zeros.
"""
from __future__ import annotations

import json

import json as _json
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from evalkit.dataset import GOLDEN_SET, KNOWN_SOURCES, GoldenSet
from evalkit.evaluators.router import confusion_matrix
from evalkit.report import HEADLINE, LOWER_IS_BETTER
from evalkit.store import DEFAULT_DB, TraceStore

router = APIRouter(prefix="/api/eval", tags=["eval"])


def _store() -> TraceStore:
    return TraceStore(DEFAULT_DB)


def _dataset() -> GoldenSet | None:
    try:
        return GoldenSet.load(GOLDEN_SET)
    except (FileNotFoundError, ValueError):
        return None


@router.get("/summary")
def summary() -> dict:
    """Every finished run with its headline metrics, newest first."""
    dataset = _dataset()
    store = _store()

    runs = []
    for info in store.list_runs():
        if not info["finished_at"]:
            continue  # a crashed run has partial traces; never report it as a result
        runs.append({
            "run_id": info["run_id"],
            "config_name": info["config_name"],
            "config_hash": info["config_hash"],
            "config": json.loads(info["config_json"]),
            "git_sha": (info["git_sha"] or "")[:8],
            "git_dirty": bool(info["git_dirty"]),
            "started_at": info["started_at"],
            "dataset_size": info["dataset_size"],
            "metrics": store.aggregate(info["run_id"]),
        })

    return {
        "has_data": bool(runs),
        "dataset": dataset.summary() if dataset else None,
        "metric_order": HEADLINE,
        "lower_is_better": sorted(LOWER_IS_BETTER),
        "runs": runs,
    }


@router.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    """One run in full: slices, the confusion matrix, and every failure."""
    store = _store()
    info = store.run_info(run_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"no such run: {run_id}")

    dataset = _dataset()
    if dataset is None:
        raise HTTPException(status_code=409, detail="golden set missing or invalid")

    by_id = {record.id: record for record in dataset}
    traces = store.traces(run_id)

    routing = store.scores_for(run_id, "route_correct")
    correctness = store.scores_for(run_id, "answer_correctness")
    hallucinated = store.scores_for(run_id, "hallucinated")

    failures = []
    for trace in traces:
        qid = trace["question_id"]
        record = by_id.get(qid)
        if record is None:
            continue

        if routing.get(qid) == 0.0:
            kind = "misrouted"
        elif hallucinated.get(qid) == 1.0:
            kind = "hallucinated"
        elif correctness.get(qid) == 0.0:
            kind = "wrong answer"
        elif not trace.get("ok"):
            kind = "errored"
        else:
            continue

        failures.append({
            "question_id": qid,
            "question": record.question,
            "kind": kind,
            "category": record.category,
            "expected_route": record.route_label if record.answerable else None,
            "actual_route": trace.get("route_predicted"),
            "answerable": record.answerable,
            "fallback_used": bool(trace.get("fallback_used")),
            "answer": (trace.get("answer") or "")[:600],
            "sql_query": trace.get("sql_query"),
            "gold_sql": record.gold_sql,
            "sources": [s.get("file") for s in (trace.get("sources") or [])],
            "gold_doc_ids": record.gold_doc_ids,
        })

    order = {"hallucinated": 0, "misrouted": 1, "wrong answer": 2, "errored": 3}
    failures.sort(key=lambda f: (order.get(f["kind"], 9), f["question_id"]))

    return {
        "run_id": run_id,
        "config_name": info["config_name"],
        "config": json.loads(info["config_json"]),
        "config_hash": info["config_hash"],
        "git_sha": (info["git_sha"] or "")[:8],
        "git_dirty": bool(info["git_dirty"]),
        "started_at": info["started_at"],
        "metrics": store.aggregate(run_id),
        "by_category": store.aggregate_by(run_id, "category", dataset),
        "by_difficulty": store.aggregate_by(run_id, "difficulty", dataset),
        "confusion": confusion_matrix(traces, dataset),
        "counts": {
            "traces": len(traces),
            "failures": len(failures),
            "fallbacks": sum(1 for t in traces if t.get("fallback_used")),
        },
        "failures": failures,
    }


@router.get("/dataset")
def dataset_detail() -> dict:
    """The golden set's composition, for the dataset panel."""
    dataset = _dataset()
    if dataset is None:
        return {
            "available": False,
            "summary": None,
            "categories": {},
            "sources": sorted(KNOWN_SOURCES),
        }

    categories: dict[str, int] = {}
    for record in dataset:
        categories[record.category] = categories.get(record.category, 0) + 1

    return {
        "available": True,
        "summary": dataset.summary(),
        "categories": dict(sorted(categories.items(), key=lambda kv: -kv[1])),
        # The policy corpus, so the UI never duplicates this list.
        "sources": sorted(KNOWN_SOURCES),
    }


# ── Ad-hoc questions ──────────────────────────────────────────────────


class TryRequest(BaseModel):
    """One question to run through the live pipeline."""

    question: str = Field(min_length=1, max_length=2000)
    # When set, the question is treated as having no answer in the corpus, so
    # the only correct behaviour is to decline. Grades abstention instead of
    # faithfulness.
    expect_unanswerable: bool = False
    judge: bool = True


@router.post("/try")
def try_question(payload: TryRequest) -> dict:
    """
    Run one question and grade what can be graded without ground truth.

    Faithfulness and relevance need only the retrieved context, so they work
    here. Correctness needs a reference answer, so it is deliberately absent:
    a playground that graded correctness against the pipeline's own output
    would always report success.
    """
    import pipeline
    import router as query_router
    from llm import has_api_key

    from evalkit.evaluators.generation import (
        GenerationEvaluator,
        _context_of,
        looks_like_refusal,
    )

    if not has_api_key():
        raise HTTPException(
            status_code=503,
            detail="No LLM API key is set. Add one to .env and restart the backend.",
        )

    question = payload.question.strip()

    # Same instrumentation the worker uses: wrap the keyword fallback so we can
    # tell whether the LLM router answered or failed over.
    keyword_route = query_router._keyword_route
    fired = {"value": False}

    def traced(q: str) -> str:
        fired["value"] = True
        return keyword_route(q)

    query_router._keyword_route = traced
    started = time.perf_counter()
    try:
        heuristic = keyword_route(question)
        result = pipeline.answer(question)
    finally:
        query_router._keyword_route = keyword_route

    trace = {
        "route": result.get("route"),
        "answer": result.get("answer"),
        "sql_query": result.get("sql_query"),
        "rows": result.get("rows"),
        "columns": result.get("columns"),
        "sources": result.get("sources"),
        "chunks": result.get("chunks"),
        "ok": result.get("ok", False),
    }

    grades: dict[str, float] = {}
    judge_note = None

    if payload.expect_unanswerable:
        abstained = looks_like_refusal(trace["answer"])
        grades["abstained"] = float(abstained)
        grades["hallucinated"] = float(not abstained)
    elif payload.judge and trace["ok"]:
        evaluator = GenerationEvaluator(use_judge=True)
        verdict = evaluator._judge(
            question, _context_of(trace), trace["answer"] or "", ""
        )
        if verdict and "error" not in verdict:
            grades["faithfulness"] = float(verdict["faithful"])
            grades["answer_relevance"] = float(verdict["relevant"])
            judge_note = verdict.get("why")
        elif verdict:
            judge_note = verdict.get("error")

    return {
        "question": question,
        "route": trace["route"],
        "keyword_route": heuristic,
        "fallback_used": fired["value"],
        "ok": trace["ok"],
        "answer": trace["answer"],
        "sql_query": trace["sql_query"],
        "columns": trace["columns"],
        "rows": (trace["rows"] or [])[:20],
        "sources": [s.get("file") for s in (trace["sources"] or [])],
        "chunks": [
            {"file": c.get("file"), "title": c.get("title"), "text": (c.get("text") or "")[:600]}
            for c in (trace["chunks"] or [])
        ],
        "elapsed": round(time.perf_counter() - started, 3),
        "grades": grades,
        "judge_note": judge_note,
        "expected_unanswerable": payload.expect_unanswerable,
    }


# ── Adding to the dataset ─────────────────────────────────────────────


class CandidateRequest(BaseModel):
    """A question on its way to the golden set, via the review queue."""

    question: str = Field(min_length=1, max_length=2000)
    route_label: Literal["sql", "rag"]
    category: str = Field(default="from_playground", max_length=64)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    answerable: bool = True
    gold_sql: str | None = None
    gold_doc_ids: list[str] | None = None
    gold_answer: str | None = None
    notes: str = ""


@router.post("/candidates")
def add_candidate(payload: CandidateRequest) -> dict:
    """
    Append to candidates.jsonl, never straight to the golden set.

    The review queue exists because a question whose ground truth is whatever
    the pipeline happened to output cannot measure the pipeline. Writing here
    keeps `make eval-promote` in the path, so nothing reaches the golden set
    without a second look.
    """
    from evalkit.dataset import GoldenRecord
    from evalkit.seed import CANDIDATES

    existing = []
    if CANDIDATES.exists():
        existing = [
            _json.loads(line)
            for line in CANDIDATES.read_text().splitlines()
            if line.strip()
        ]

    record = {
        "id": f"cand_ui_{len(existing):04d}",
        "question": payload.question.strip(),
        "route_label": payload.route_label,
        "category": payload.category or "from_playground",
        "difficulty": payload.difficulty,
        "gold_sql": payload.gold_sql,
        "gold_answer": payload.gold_answer,
        "gold_doc_ids": payload.gold_doc_ids,
        "answerable": payload.answerable,
        "notes": payload.notes,
    }

    # Validate against the real schema now, so a malformed row cannot sit in
    # the queue until promote time.
    try:
        GoldenRecord(**record)
    except Exception as exc:  # noqa: BLE001 - report the validation message as-is
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if any(c.get("question", "").strip().lower() == record["question"].lower()
           for c in existing):
        raise HTTPException(status_code=409, detail="That question is already queued.")

    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES.open("a") as handle:
        handle.write(_json.dumps({**record, "reviewed": False}) + "\n")

    return {
        "queued": True,
        "id": record["id"],
        "pending": len(existing) + 1,
        "next_step": "Review it, set reviewed: true, then run make eval-promote.",
    }
