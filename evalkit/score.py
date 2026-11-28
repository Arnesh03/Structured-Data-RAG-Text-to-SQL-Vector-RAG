"""
Scores a recorded run. Reads `results`, writes `scores`, never re-runs anything.

This is where the separation in the design pays off: adding a metric and
re-running this file re-scores every historical run for the cost of the judge
cache misses alone.
"""
from __future__ import annotations

import argparse
import sys

from evalkit.dataset import GOLDEN_SET, GoldenSet
from evalkit.evaluators import (
    GenerationEvaluator,
    RetrievalEvaluator,
    RouterEvaluator,
    SQLEvaluator,
)
from evalkit.store import DEFAULT_DB, TraceStore


def score_run(run_id: str, dataset_path=GOLDEN_SET, db_path=DEFAULT_DB,
              use_judge: bool = True) -> dict[str, float]:
    store = TraceStore(db_path)
    dataset = GoldenSet.load(dataset_path)
    by_id = {record.id: record for record in dataset}

    evaluators = [
        RouterEvaluator(),
        SQLEvaluator(),
        RetrievalEvaluator(),
        GenerationEvaluator(use_judge=use_judge),
    ]

    traces = store.traces(run_id)
    if not traces:
        print(f"No traces found for {run_id}.", file=sys.stderr)
        return {}

    print(f"Scoring {len(traces)} traces for {run_id}"
          f"{'' if use_judge else ' (deterministic metrics only)'}")

    for trace in traces:
        record = by_id.get(trace["question_id"])
        if record is None:
            continue  # trace from an older version of the dataset

        metrics: dict[str, float] = {}
        details: dict[str, dict] = {}
        for evaluator in evaluators:
            scored, detail = evaluator.score(trace, record)
            metrics.update(scored)
            if detail:
                details[evaluator.name] = detail

        if metrics:
            store.write_scores(run_id, record.id, metrics, details)

    aggregate = store.aggregate(run_id)
    for metric, value in aggregate.items():
        print(f"  {metric:<26} {value:.3f}")
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a recorded run.")
    parser.add_argument("run_id", nargs="?", help="omit to score the latest baseline run")
    parser.add_argument("--dataset", default=str(GOLDEN_SET))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--no-judge", action="store_true",
                        help="deterministic metrics only, no LLM calls")
    args = parser.parse_args()

    run_id = args.run_id or TraceStore(args.db).latest_run("baseline")
    if not run_id:
        print("No run to score. Run `make eval` first.", file=sys.stderr)
        return 1

    score_run(run_id, args.dataset, args.db, use_judge=not args.no_judge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
