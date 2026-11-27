"""
The CI gate: fails a pull request that makes the system measurably worse.

Compares a run against `reports/baseline.json`, which is committed to the repo
and only moves by an explicit commit. A baseline that drifts on its own gates
nothing.
"""
from __future__ import annotations

import argparse
import json
import sys

from evalkit.report import BASELINE_JSON, LOWER_IS_BETTER
from evalkit.store import DEFAULT_DB, TraceStore

# Metrics that must never get worse at all, because a regression here is a
# safety problem rather than a quality tradeoff.
ZERO_TOLERANCE = ("hallucinated", "sql_invalid")

DEFAULT_THRESHOLD = 0.03


def check(run_id: str, db_path=DEFAULT_DB, threshold: float = DEFAULT_THRESHOLD) -> int:
    if not BASELINE_JSON.exists():
        print(f"No {BASELINE_JSON}; nothing to gate against.")
        print("Create it once with: make eval-save-baseline")
        return 0

    baseline = json.loads(BASELINE_JSON.read_text())["metrics"]
    current = TraceStore(db_path).aggregate(run_id)

    failures, notes = [], []
    for metric, base_value in sorted(baseline.items()):
        if metric not in current:
            notes.append(f"  {metric}: not measured in this run")
            continue

        delta = current[metric] - base_value
        worse = delta > 0 if metric in LOWER_IS_BETTER else delta < 0
        if not worse:
            continue

        limit = 0.0 if metric in ZERO_TOLERANCE else threshold
        if abs(delta) > limit:
            failures.append(
                f"  {metric}: {base_value:.3f} -> {current[metric]:.3f} "
                f"({delta:+.3f}, limit {limit:.3f})"
            )

    print(f"Gate for {run_id} against baseline {json.loads(BASELINE_JSON.read_text())['run_id']}")
    for note in notes:
        print(note)

    if failures:
        print(f"\nFAILED: {len(failures)} metric(s) regressed")
        for failure in failures:
            print(failure)
        return 1

    print("\nPASSED: no metric regressed beyond its limit")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate a run against the committed baseline.")
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    run_id = args.run_id or TraceStore(args.db).latest_run("ci")
    if not run_id:
        print("No run to gate.", file=sys.stderr)
        return 1
    return check(run_id, args.db, args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
