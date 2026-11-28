"""
The CI gate: fails a pull request that makes the system measurably worse.

Two numbers in here are empirical rather than chosen, and both come from
running the same unchanged pipeline twice (runs baseline-415fc924 and
baseline-5d8d95aa):

  SQL execution accuracy moved 0.481 -> 0.536 across those runs with nothing
  in that path changed - same database, same questions, temperature 0. That
  5.4-point swing is the model's own run-to-run variance.

So a threshold below ~5 points does not detect regressions, it detects noise.
NOISE_FLOOR records the measurement and DEFAULT_THRESHOLD sits above it.

The gate also runs the FULL golden set rather than a sample. Comparing a
20-question stratified sample against a baseline computed over 66 questions
is not comparing like with like: precision@k over 11 RAG questions differs
from precision@k over 26 by sampling alone, before any code changes.
"""
from __future__ import annotations

import argparse
import json
import sys

from evalkit.report import BASELINE_JSON, LOWER_IS_BETTER
from evalkit.store import DEFAULT_DB, TraceStore

# Measured, not guessed. See the module docstring.
NOISE_FLOOR = 0.054

# Comfortably above the noise floor, so a failure means something.
DEFAULT_THRESHOLD = 0.08

# Metrics where a regression is a safety problem rather than a quality
# tradeoff, held to a tighter bar. Not zero: `hallucinated` is measured over 12
# questions, so a single flip moves it 0.083, and a gate that fails on one
# flipped question fails constantly and gets ignored.
SAFETY_METRICS = ("hallucinated", "sql_invalid")
SAFETY_THRESHOLD = 0.05


def compare(
    baseline: dict[str, float],
    current: dict[str, float],
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[list[str], list[str]]:
    """
    Pure comparison: returns (failures, notes).

    Kept free of file and database access so it can be tested directly. The
    caller supplies the numbers; this decides what they mean.
    """
    failures, notes = [], []

    for metric, base_value in sorted(baseline.items()):
        if metric not in current:
            notes.append(f"  {metric}: not measured in this run")
            continue

        delta = current[metric] - base_value
        worse = delta > 0 if metric in LOWER_IS_BETTER else delta < 0
        if not worse:
            continue

        limit = SAFETY_THRESHOLD if metric in SAFETY_METRICS else threshold
        if abs(delta) > limit:
            failures.append(
                f"  {metric}: {base_value:.3f} -> {current[metric]:.3f} "
                f"({delta:+.3f}, limit {limit:.3f})"
            )

    return failures, notes


def check(run_id: str, db_path=DEFAULT_DB, threshold: float = DEFAULT_THRESHOLD) -> int:
    if not BASELINE_JSON.exists():
        print(f"No {BASELINE_JSON}; nothing to gate against.")
        print("Create it once with: make eval-save-baseline")
        return 0

    payload = json.loads(BASELINE_JSON.read_text())
    current = TraceStore(db_path).aggregate(run_id)

    if not current:
        print(f"No scores recorded for {run_id}; nothing to compare.", file=sys.stderr)
        return 1

    failures, notes = compare(payload["metrics"], current, threshold)

    print(f"Gate for {run_id} against baseline {payload['run_id']}")
    print(f"  threshold {threshold:.3f}, safety {SAFETY_THRESHOLD:.3f}, "
          f"measured noise floor {NOISE_FLOOR:.3f}")
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

    run_id = args.run_id or TraceStore(args.db).latest_run("baseline")
    if not run_id:
        print("No run to gate.", file=sys.stderr)
        return 1
    return check(run_id, args.db, args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
