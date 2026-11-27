"""
Turns a scored run into something a person reads.

Two outputs, and the second is the one that matters for a pull request:

  report(run_id)   a single run: headline metrics, slices, confusion matrix,
                   and the worst failures with full context
  compare(runs)    the ablation table, one row per config, baseline first

A report always leads with the finding, not with the configuration. If you
cannot write the first line as a sentence with a number in it, the run has not
told you anything yet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evalkit.dataset import GOLDEN_SET, GoldenSet
from evalkit.evaluators.router import confusion_matrix
from evalkit.store import DEFAULT_DB, TraceStore

REPORTS_DIR = Path(__file__).parent.parent / "reports"
BASELINE_JSON = REPORTS_DIR / "baseline.json"

# Metrics worth putting at the top of a report, in reading order.
HEADLINE = [
    "route_correct",
    "keyword_correct",
    "fallback_used",
    "sql_execution_accuracy",
    "sql_invalid",
    "precision_at_k",
    "recall_at_k",
    "mrr",
    "ndcg_at_k",
    "faithfulness",
    "answer_relevance",
    "answer_correctness",
    "abstained",
    "hallucinated",
]

# Metrics where lower is better, so a diff knows which way is a regression.
LOWER_IS_BETTER = {"sql_invalid", "hallucinated", "fallback_used"}


def _fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out)


def report(run_id: str, dataset_path=GOLDEN_SET, db_path=DEFAULT_DB,
           baseline_run: str | None = None) -> str:
    store = TraceStore(db_path)
    dataset = GoldenSet.load(dataset_path)
    info = store.run_info(run_id)
    if info is None:
        raise SystemExit(f"no such run: {run_id}")

    aggregate = store.aggregate(run_id)
    traces = store.traces(run_id)

    config = json.loads(info["config_json"])
    dirty = " (working tree dirty)" if info["git_dirty"] else ""

    lines = [
        f"# Eval report: {info['config_name']}",
        "",
        f"Run `{run_id}` · config `{info['config_hash']}` · "
        f"git `{(info['git_sha'] or 'unknown')[:8]}`{dirty} · {info['started_at']}",
        "",
        "## Settings",
        "",
        "```",
        "\n".join(f"{k} = {v}" for k, v in sorted(config.items())) or "(pipeline defaults)",
        "```",
        "",
        "## Headline metrics",
        "",
    ]

    rows = [[m, _fmt(aggregate[m])] for m in HEADLINE if m in aggregate]
    extra = sorted(set(aggregate) - set(HEADLINE))
    rows += [[m, _fmt(aggregate[m])] for m in extra]
    lines += [_table(["metric", "value"], rows), ""]

    # ── Baseline diff ─────────────────────────────────────────────────
    if baseline_run and baseline_run != run_id:
        base = store.aggregate(baseline_run)
        diff_rows = []
        for metric in sorted(set(aggregate) & set(base)):
            delta = aggregate[metric] - base[metric]
            if abs(delta) < 0.0005:
                continue
            better = delta < 0 if metric in LOWER_IS_BETTER else delta > 0
            diff_rows.append([metric, _fmt(base[metric]), _fmt(aggregate[metric]),
                              f"{delta:+.3f}", "better" if better else "worse"])
        if diff_rows:
            lines += ["## Change from baseline", "",
                      _table(["metric", "baseline", "this run", "delta", ""], diff_rows), ""]

    # ── Slices ────────────────────────────────────────────────────────
    for field in ("category", "difficulty"):
        sliced = store.aggregate_by(run_id, field, dataset)
        if not sliced:
            continue
        metrics = [m for m in HEADLINE
                   if any(m in values for values in sliced.values())][:5]
        if not metrics:
            continue
        rows = [[bucket] + [_fmt(values.get(m)) for m in metrics]
                for bucket, values in sliced.items()]
        lines += [f"## By {field}", "", _table([field] + metrics, rows), ""]

    # ── Confusion matrix ──────────────────────────────────────────────
    matrix = confusion_matrix(traces, dataset)
    lines += [
        "## Router confusion matrix",
        "",
        "Rows are the correct arm, columns are the arm chosen.",
        "",
        _table(["expected \\ predicted", "sql", "rag", "none"],
               [[expected, str(counts["sql"]), str(counts["rag"]), str(counts["None"])]
                for expected, counts in matrix.items()]),
        "",
    ]

    # ── Worst failures ────────────────────────────────────────────────
    by_id = {r.id: r for r in dataset}
    correctness = store.scores_for(run_id, "answer_correctness")
    routing = store.scores_for(run_id, "route_correct")

    failures = []
    for trace in traces:
        qid = trace["question_id"]
        record = by_id.get(qid)
        if record is None:
            continue
        if routing.get(qid) == 0.0:
            failures.append((qid, record, trace, "misrouted"))
        elif correctness.get(qid) == 0.0:
            failures.append((qid, record, trace, "wrong answer"))
        elif not trace.get("ok"):
            failures.append((qid, record, trace, "errored"))

    lines += [f"## Failures ({len(failures)})", ""]
    if not failures:
        lines.append("None. Check that the dataset is actually hard enough.")
    for qid, record, trace, why in failures[:20]:
        lines += [
            f"**{qid}** · {why} · expected `{record.route_label}`, "
            f"got `{trace.get('route_predicted')}`"
            + ("  · keyword fallback fired" if trace.get("fallback_used") else ""),
            "",
            f"> {record.question}",
            "",
            f"{(trace.get('answer') or '(no answer)')[:400]}",
            "",
        ]
        if trace.get("sql_query"):
            lines += ["```sql", trace["sql_query"], "```", ""]

    text = "\n".join(lines)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{run_id}.md"
    path.write_text(text)
    print(f"wrote {path}")
    return text


def compare(run_ids: list[str], db_path=DEFAULT_DB) -> str:
    """The ablation table: one row per run, baseline first."""
    store = TraceStore(db_path)
    metrics = [m for m in HEADLINE]

    rows = []
    for run_id in run_ids:
        info = store.run_info(run_id)
        if info is None:
            continue
        aggregate = store.aggregate(run_id)
        rows.append([info["config_name"]] + [_fmt(aggregate.get(m)) for m in metrics])

    present = [i for i, m in enumerate(metrics)
               if any(row[i + 1] != "—" for row in rows)]
    headers = ["config"] + [metrics[i] for i in present]
    rows = [[row[0]] + [row[i + 1] for i in present] for row in rows]

    text = "\n".join([
        "# Ablation grid",
        "",
        "One variable changes per row. A difference here is attributable; a",
        "difference in a grid search is not.",
        "",
        _table(headers, rows),
        "",
    ])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "ablations.md").write_text(text)
    print(f"wrote {REPORTS_DIR / 'ablations.md'}")
    return text


def save_baseline(run_id: str, db_path=DEFAULT_DB) -> None:
    """Commit a run's metrics as the gate CI compares against."""
    store = TraceStore(db_path)
    payload = {"run_id": run_id, "metrics": store.aggregate(run_id)}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"wrote {BASELINE_JSON} from {run_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render eval reports.")
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--dataset", default=str(GOLDEN_SET))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--baseline", help="run_id to diff against")
    parser.add_argument("--compare", nargs="+", help="render the ablation table")
    parser.add_argument("--save-baseline", action="store_true")
    args = parser.parse_args()

    if args.compare:
        print(compare(args.compare, args.db))
        return 0

    store = TraceStore(args.db)
    run_id = args.run_id or store.latest_run("baseline")
    if not run_id:
        print("No run to report on. Run `make eval` first.")
        return 1

    if args.save_baseline:
        save_baseline(run_id, args.db)
        return 0

    baseline = args.baseline or (store.latest_run("baseline") if run_id else None)
    report(run_id, args.dataset, args.db, baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
