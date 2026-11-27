"""
Read-only HTTP surface over the trace store, for the Evals tab in the web UI.

Everything here is a projection of what `evalkit.store` already holds. No
scoring, no running: a dashboard that could mutate results would be a
dashboard you could not trust.

The whole router degrades to `has_data: false` when no run has been recorded
yet, so the UI can explain how to produce one instead of rendering zeros.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from evalkit.dataset import GOLDEN_SET, GoldenSet
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
        return {"available": False, "summary": None, "categories": {}}

    categories: dict[str, int] = {}
    for record in dataset:
        categories[record.category] = categories.get(record.category, 0) + 1

    return {
        "available": True,
        "summary": dataset.summary(),
        "categories": dict(sorted(categories.items(), key=lambda kv: -kv[1])),
    }
