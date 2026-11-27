"""
Validates the LLM judge against your own labels, and reports Cohen's kappa.

An LLM grading an LLM has no credibility until you show it agrees with a human.
This is the step almost no portfolio project includes, and it costs half a day.

Two commands:

  --export 50   writes a labeling file: a stratified sample with the judge's
                verdict HIDDEN, so you cannot anchor on it
  --score       reads your labels back and reports agreement

Interpretation: above ~0.8 is strong and the automated numbers stand on their
own; 0.6-0.8 is usable with the caveat stated; below 0.6 means the judge prompt
needs work. Reporting a kappa of 0.71 honestly beats reporting a faithfulness
of 0.94 you never checked.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evalkit.dataset import GOLDEN_SET, GoldenSet
from evalkit.store import DEFAULT_DB, TraceStore

LABELS_DIR = Path(__file__).parent.parent / "reports"
LABEL_FILE = LABELS_DIR / "judge_labels.jsonl"

JUDGED = ("faithfulness", "answer_correctness")


def cohens_kappa(a: list[int], b: list[int]) -> float:
    """
    Agreement between two binary labelers, corrected for chance.

    Plain percent agreement flatters a judge on an unbalanced set: if 90% of
    answers are faithful, always saying "faithful" scores 90%. Kappa removes
    that floor.
    """
    if not a or len(a) != len(b):
        return float("nan")

    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n

    expected = 0.0
    for value in (0, 1):
        expected += (a.count(value) / n) * (b.count(value) / n)

    if expected == 1.0:
        return float("nan")  # both labelers were constant; kappa is undefined
    return (observed - expected) / (1 - expected)


def export(run_id: str, n: int, dataset_path=GOLDEN_SET, db_path=DEFAULT_DB) -> None:
    store = TraceStore(db_path)
    dataset = GoldenSet.load(dataset_path)
    by_id = {r.id: r for r in dataset}

    faith = store.scores_for(run_id, "faithfulness")
    correct = store.scores_for(run_id, "answer_correctness")
    if not faith:
        raise SystemExit(f"{run_id} has no judged scores yet; run `make eval-score` first.")

    # Stratify across the judge's own verdicts, so the sample is not all the
    # easy agreements.
    buckets: dict[tuple, list[str]] = {}
    for qid in faith:
        key = (faith.get(qid), correct.get(qid))
        buckets.setdefault(key, []).append(qid)

    rng = random.Random(0)
    for ids in buckets.values():
        rng.shuffle(ids)

    picked: list[str] = []
    while len(picked) < n and any(buckets.values()):
        for key in sorted(buckets, key=str):
            if buckets[key] and len(picked) < n:
                picked.append(buckets[key].pop())

    traces = {t["question_id"]: t for t in store.traces(run_id)}
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    with LABEL_FILE.open("w") as handle:
        for qid in sorted(picked):
            record = by_id.get(qid)
            trace = traces.get(qid, {})
            handle.write(json.dumps({
                "run_id": run_id,
                "question_id": qid,
                "question": record.question if record else "",
                "answer": trace.get("answer"),
                "sql_query": trace.get("sql_query"),
                "sources": [s.get("file") for s in (trace.get("sources") or [])],
                # Label these two yourself. The judge's verdict is deliberately
                # not in this file: seeing it first makes you agree with it.
                "human_faithful": None,
                "human_correct": None,
            }) + "\n")

    print(f"wrote {len(picked)} rows to {LABEL_FILE}")
    print("Fill in human_faithful and human_correct (0 or 1), then run:")
    print("  make eval-kappa")


def score(db_path=DEFAULT_DB) -> dict[str, float]:
    if not LABEL_FILE.exists():
        raise SystemExit(f"{LABEL_FILE} not found. Run `make eval-judge-export` first.")

    rows = [json.loads(line) for line in LABEL_FILE.read_text().splitlines() if line.strip()]
    labeled = [r for r in rows if r.get("human_faithful") is not None
               and r.get("human_correct") is not None]

    if not labeled:
        raise SystemExit(f"No labels filled in yet in {LABEL_FILE}.")

    store = TraceStore(db_path)
    run_id = labeled[0]["run_id"]
    judge_faith = store.scores_for(run_id, "faithfulness")
    judge_correct = store.scores_for(run_id, "answer_correctness")

    results = {}
    for name, human_key, judge_scores in (
        ("faithfulness", "human_faithful", judge_faith),
        ("answer_correctness", "human_correct", judge_correct),
    ):
        pairs = [(int(r[human_key]), int(judge_scores[r["question_id"]]))
                 for r in labeled if r["question_id"] in judge_scores]
        if not pairs:
            continue
        human, judge = [p[0] for p in pairs], [p[1] for p in pairs]
        kappa = cohens_kappa(human, judge)
        agreement = sum(1 for h, j in pairs if h == j) / len(pairs)
        results[name] = kappa
        print(f"{name:<20} n={len(pairs):<4} agreement={agreement:.3f}  kappa={kappa:.3f}")

    print(f"\nLabeled {len(labeled)}/{len(rows)} rows.")
    print("Put these numbers in the README next to the judged metrics, whatever they are.")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the LLM judge against human labels.")
    parser.add_argument("--export", type=int, metavar="N", help="write N rows to label")
    parser.add_argument("--run-id")
    parser.add_argument("--dataset", default=str(GOLDEN_SET))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    if args.export:
        run_id = args.run_id or TraceStore(args.db).latest_run("baseline")
        if not run_id:
            print("No run found. Run `make eval` first.")
            return 1
        export(run_id, args.export, args.dataset, args.db)
    else:
        score(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
