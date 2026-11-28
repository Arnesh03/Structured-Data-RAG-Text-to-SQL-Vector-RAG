"""
Orchestrates runs: one subprocess per config, raw traces into the store.

The runner owns no evaluation logic at all. It decides what to execute and
where the output goes; `evaluators` decide what any of it is worth.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from evalkit.cache import index_dir_for
from evalkit.config import EvalConfig, load_all
from evalkit.dataset import GOLDEN_SET, GoldenSet
from evalkit.store import DEFAULT_DB, TraceStore

PROJECT_ROOT = Path(__file__).parent.parent


def run_config(
    config: EvalConfig,
    dataset_path: str | Path = GOLDEN_SET,
    db_path: str | Path = DEFAULT_DB,
    limit: int = 0,
    sample: int = 0,
) -> str | None:
    """Execute one config in a fresh process. Returns its run_id, or None if it failed."""
    dataset = GoldenSet.load(dataset_path)
    size = sample or limit or len(dataset)

    store = TraceStore(db_path)
    run_id = store.start_run(config, str(dataset_path), size)

    env = os.environ.copy()
    env.update(config.env())
    # Each chunk/embedding combination gets its own index directory, so configs
    # that share those settings share the built index instead of clobbering it.
    env["VECTORSTORE_DIR"] = str(index_dir_for(config.index_hash))

    print(f"\n=== {config.name} ({config.config_hash}) ===")
    if config.as_dict:
        print("    " + "  ".join(f"{k}={v}" for k, v in sorted(config.as_dict.items())))

    command = [
        sys.executable, "-m", "evalkit.worker",
        "--run-id", run_id,
        "--dataset", str(dataset_path),
        "--db", str(db_path),
    ]
    if sample:
        command += ["--sample", str(sample)]
    elif limit:
        command += ["--limit", str(limit)]

    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if completed.returncode != 0:
        print(f"    FAILED (exit {completed.returncode}); run {run_id} left unfinished")
        return None

    store.finish_run(run_id)
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the eval harness.")
    parser.add_argument("--config", help="path to one config YAML; omit for all of them")
    parser.add_argument("--dataset", default=str(GOLDEN_SET))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=0, help="first N questions")
    parser.add_argument("--sample", type=int, default=0, help="stratified sample of N")
    parser.add_argument("--score", action="store_true", help="score each run when it finishes")
    args = parser.parse_args()

    configs = [EvalConfig.from_yaml(args.config)] if args.config else load_all()
    if not configs:
        print("No configs found under configs/.", file=sys.stderr)
        return 1

    run_ids = []
    for config in configs:
        run_id = run_config(config, args.dataset, args.db, args.limit, args.sample)
        if run_id:
            run_ids.append(run_id)

    if args.score and run_ids:
        from evalkit.score import score_run
        for run_id in run_ids:
            score_run(run_id, args.dataset, args.db)

    print(f"\n{len(run_ids)}/{len(configs)} run(s) completed.")
    for run_id in run_ids:
        print(f"  {run_id}")
    return 0 if len(run_ids) == len(configs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
