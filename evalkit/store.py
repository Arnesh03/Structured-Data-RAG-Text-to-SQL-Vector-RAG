"""
The trace store: one SQLite file holding every run, trace and score.

Three tables, and the split between them is the point of the whole design:

  runs     one row per (config, dataset) execution, stamped with the git SHA
  results  the RAW output of the pipeline, with no judgement applied
  scores   metric values, written by evaluators reading `results`

Because scoring never touches `results`, adding a metric re-scores every past
run without re-running the pipeline or paying for the LLM calls again.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = PROJECT_ROOT / "reports" / "traces.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    config_name   TEXT NOT NULL,
    config_hash   TEXT NOT NULL,
    config_json   TEXT NOT NULL,
    git_sha       TEXT,
    git_dirty     INTEGER,
    dataset_path  TEXT,
    dataset_size  INTEGER,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS results (
    run_id          TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    route_predicted TEXT,
    keyword_route   TEXT,
    answer          TEXT,
    sql_query       TEXT,
    rows_json       TEXT,
    sources_json    TEXT,
    chunks_json     TEXT,
    fallback_used   INTEGER DEFAULT 0,
    ok              INTEGER DEFAULT 1,
    error           TEXT,
    elapsed         REAL,
    route_elapsed   REAL,
    PRIMARY KEY (run_id, question_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS scores (
    run_id      TEXT NOT NULL,
    question_id TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       REAL,
    detail      TEXT,
    scored_at   TEXT NOT NULL,
    PRIMARY KEY (run_id, question_id, metric)
);

CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_scores_run ON scores(run_id, metric);
"""


def git_state() -> tuple[str | None, bool]:
    """Current commit and whether the tree is dirty, for provenance."""
    def run(args: list[str]) -> str | None:
        try:
            out = subprocess.run(
                args, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5,
            )
            return out.stdout.strip() if out.returncode == 0 else None
        except Exception:  # noqa: BLE001 - provenance is best-effort
            return None

    sha = run(["git", "rev-parse", "HEAD"])
    status = run(["git", "status", "--porcelain"])
    return sha, bool(status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TraceStore:
    """Thin, explicit wrapper over the SQLite file. No ORM, no magic."""

    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── Runs ──────────────────────────────────────────────────────────

    def start_run(self, config, dataset_path: str, dataset_size: int) -> str:
        run_id = f"{config.name}-{uuid.uuid4().hex[:8]}"
        sha, dirty = git_state()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, config_name, config_hash, config_json,"
                " git_sha, git_dirty, dataset_path, dataset_size, started_at, notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, config.name, config.config_hash,
                 json.dumps(config.as_dict, sort_keys=True), sha, int(dirty),
                 str(dataset_path), dataset_size, _now(), config.notes),
            )
        return run_id

    def finish_run(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE runs SET finished_at = ? WHERE run_id = ?", (_now(), run_id))

    def latest_run(self, config_name: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id FROM runs WHERE config_name = ? AND finished_at IS NOT NULL"
                " ORDER BY started_at DESC LIMIT 1",
                (config_name,),
            ).fetchone()
        return row["run_id"] if row else None

    def run_info(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ── Raw traces ────────────────────────────────────────────────────

    def record(self, run_id: str, question_id: str, trace: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO results (run_id, question_id, route_predicted,"
                " keyword_route, answer, sql_query, rows_json, sources_json, chunks_json,"
                " fallback_used, ok, error, elapsed, route_elapsed)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id, question_id, trace.get("route"), trace.get("keyword_route"),
                    trace.get("answer"),
                    trace.get("sql_query"),
                    json.dumps(trace.get("rows")) if trace.get("rows") is not None else None,
                    json.dumps(trace.get("sources")) if trace.get("sources") is not None else None,
                    json.dumps(trace.get("chunks")) if trace.get("chunks") is not None else None,
                    int(bool(trace.get("fallback_used"))), int(bool(trace.get("ok", True))),
                    trace.get("error"), trace.get("elapsed"), trace.get("route_elapsed"),
                ),
            )

    def traces(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM results WHERE run_id = ? ORDER BY question_id", (run_id,)
            ).fetchall()
        out = []
        for row in rows:
            trace = dict(row)
            trace["rows"] = json.loads(trace["rows_json"]) if trace["rows_json"] else None
            trace["sources"] = json.loads(trace["sources_json"]) if trace["sources_json"] else None
            trace["chunks"] = json.loads(trace["chunks_json"]) if trace["chunks_json"] else None
            out.append(trace)
        return out

    # ── Scores ────────────────────────────────────────────────────────

    def write_scores(self, run_id: str, question_id: str, scores: dict[str, float],
                     detail: dict | None = None) -> None:
        stamp = _now()
        payload = json.dumps(detail) if detail else None
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO scores (run_id, question_id, metric, value,"
                " detail, scored_at) VALUES (?,?,?,?,?,?)",
                [(run_id, question_id, metric, value, payload, stamp)
                 for metric, value in scores.items()],
            )

    def aggregate(self, run_id: str) -> dict[str, float]:
        """Mean of every metric across the run, which is what a report leads with."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT metric, AVG(value) AS mean, COUNT(*) AS n FROM scores"
                " WHERE run_id = ? AND value IS NOT NULL GROUP BY metric ORDER BY metric",
                (run_id,),
            ).fetchall()
        return {r["metric"]: r["mean"] for r in rows}

    def aggregate_by(self, run_id: str, field: str, dataset) -> dict[str, dict[str, float]]:
        """Mean of every metric, sliced by a golden-set field. Where findings live."""
        bucket_of = {r.id: str(getattr(r, field)) for r in dataset}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT question_id, metric, value FROM scores"
                " WHERE run_id = ? AND value IS NOT NULL", (run_id,),
            ).fetchall()

        sums: dict[str, dict[str, list[float]]] = {}
        for row in rows:
            bucket = bucket_of.get(row["question_id"])
            if bucket is None:
                continue
            sums.setdefault(bucket, {}).setdefault(row["metric"], []).append(row["value"])

        return {
            bucket: {metric: sum(vals) / len(vals) for metric, vals in metrics.items()}
            for bucket, metrics in sorted(sums.items())
        }

    def scores_for(self, run_id: str, metric: str) -> dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT question_id, value FROM scores WHERE run_id = ? AND metric = ?",
                (run_id, metric),
            ).fetchall()
        return {r["question_id"]: r["value"] for r in rows}
