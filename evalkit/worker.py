"""
Runs ONE config over the golden set, in its own process.

A fresh process per config is deliberate. `config.py` reads its settings at
import time and several pipeline functions are `lru_cache`d, so mutating the
environment inside a long-lived process would leave stale values behind and
quietly evaluate the wrong thing. A subprocess has none of those problems, and
it makes the grid parallelizable later for free.

The parent sets the environment; this module just runs and records. It writes
RAW output only. No scoring happens here.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one eval config.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sample", type=int, default=0,
                        help="stratified sample size, used by CI")
    args = parser.parse_args()

    # Imported AFTER the parent has set the environment, so config.py picks up
    # this run's overrides rather than the defaults.
    import pipeline
    import router
    from llm import has_api_key

    from evalkit.dataset import GoldenSet
    from evalkit.store import TraceStore

    if not has_api_key():
        print("ERROR: no LLM API key is set, so the pipeline cannot answer anything.\n"
              "       Put a key in .env (see .env.example) before running the harness.",
              file=sys.stderr)
        return 2

    dataset = GoldenSet.load(args.dataset)
    if args.sample:
        dataset = dataset.stratified_sample(args.sample)
    elif args.limit:
        dataset = GoldenSet(dataset.records[: args.limit])

    store = TraceStore(args.db)

    # ── Instrument the router's keyword fallback ──────────────────────
    # `router.route_query` silently falls back to a keyword heuristic when the
    # LLM errors or returns something unparseable. Wrapping it is how we learn
    # how often that happens, which is a number no tutorial project has.
    keyword_route = router._keyword_route
    fired = {"value": False}

    def traced_keyword_route(question: str) -> str:
        fired["value"] = True
        return keyword_route(question)

    router._keyword_route = traced_keyword_route

    pipeline.initialize(warm=True)

    total = len(dataset)
    print(f"Running {total} questions as {args.run_id}")
    started = time.perf_counter()

    for index, record in enumerate(dataset, start=1):
        fired["value"] = False

        # The heuristic's own prediction, computed without the LLM. Comparing
        # it to the LLM's answer is free once we are here anyway.
        try:
            heuristic = keyword_route(record.question)
        except Exception:  # noqa: BLE001 - never let instrumentation break a run
            heuristic = None

        try:
            result = pipeline.answer(record.question)
            trace = {
                "route": result.get("route"),
                "keyword_route": heuristic,
                "answer": result.get("answer"),
                "sql_query": result.get("sql_query"),
                "rows": result.get("rows"),
                "sources": result.get("sources"),
                "chunks": result.get("chunks"),
                "ok": result.get("ok", False),
                "error": None if result.get("ok") else result.get("answer"),
                "elapsed": result.get("elapsed"),
                "route_elapsed": result.get("route_elapsed"),
                "fallback_used": fired["value"],
            }
        except Exception as exc:  # noqa: BLE001 - one bad question must not end the run
            trace = {
                "route": None, "keyword_route": heuristic, "answer": None,
                "ok": False, "error": f"{type(exc).__name__}: {exc}",
                "fallback_used": fired["value"],
            }

        store.record(args.run_id, record.id, trace)

        flag = "!" if trace.get("fallback_used") else " "
        status = "ok " if trace.get("ok") else "ERR"
        print(f"  [{index:>3}/{total}] {status}{flag} {record.id} -> {trace.get('route')}")

    elapsed = time.perf_counter() - started
    print(f"Done in {elapsed:.1f}s ({elapsed / total:.2f}s per question)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
