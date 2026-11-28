"""
Text-to-SQL evaluation. Deterministic.

Execution accuracy is the only metric here that means anything: does the
generated query return the same rows as the gold query? String-matching SQL
punishes a correct query for choosing a different alias, and rewards a broken
one for looking familiar.

The comparison rule, stated so it can be argued with:

  - result sets are compared as MULTISETS of rows, so duplicates count
  - row order is ignored UNLESS the gold query contains ORDER BY
  - column order is ignored: each row's cells are sorted before comparison
  - floats are rounded to 4 decimal places
  - None and empty string are distinct

Write this down in the README. It is exactly the detail an interviewer uses to
find out whether you built the harness or cloned it.
"""
from __future__ import annotations

FLOAT_PRECISION = 4


def normalize_cell(value) -> str:
    """One cell to a comparable string."""
    if value is None:
        return "\x00NULL"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{round(value, FLOAT_PRECISION):.{FLOAT_PRECISION}f}"
    if isinstance(value, int):
        return f"{float(value):.{FLOAT_PRECISION}f}"  # 5 and 5.0 are the same answer
    return str(value).strip()


def normalize_rows(rows, ordered: bool) -> list:
    """A result set to a comparable form."""
    if rows is None:
        return []
    normalized = [tuple(sorted(normalize_cell(cell) for cell in row)) for row in rows]
    return normalized if ordered else sorted(normalized)


class SQLEvaluator:
    name = "sql"
    deterministic = True

    def __init__(self):
        self._gold_cache: dict[str, list | None] = {}

    def _gold_rows(self, gold_sql: str):
        """Execute the gold query once per process and remember the result."""
        if gold_sql in self._gold_cache:
            return self._gold_cache[gold_sql]
        try:
            from sql_chain import run_query
            _columns, rows = run_query(gold_sql)
        except Exception:  # noqa: BLE001 - a broken gold query is a dataset bug
            rows = None
        self._gold_cache[gold_sql] = rows
        return rows

    def score(self, trace: dict, record) -> tuple[dict[str, float], dict]:
        # Only score questions that actually went down the SQL arm with a gold
        # query to compare against.
        if record.route_label != "sql" or not record.answerable or not record.gold_sql:
            return {}, {}

        generated = trace.get("sql_query")
        if trace.get("route_predicted") != "sql":
            # Misrouted: the router already lost this one. Scoring it as a SQL
            # failure too would double-count the same mistake.
            return {"sql_attempted": 0.0}, {"reason": "misrouted"}

        if not generated:
            return {"sql_attempted": 1.0, "sql_invalid": 1.0, "sql_execution_accuracy": 0.0}, \
                   {"reason": "no query generated"}

        gold_rows = self._gold_rows(record.gold_sql)
        if gold_rows is None:
            return {}, {"error": "gold_sql failed to execute; fix the dataset"}

        ordered = "order by" in record.gold_sql.lower()
        predicted_rows = trace.get("rows")

        invalid = 1.0 if predicted_rows is None and not trace.get("ok") else 0.0
        match = float(
            normalize_rows(predicted_rows, ordered) == normalize_rows(gold_rows, ordered)
        )

        metrics = {
            "sql_attempted": 1.0,
            "sql_invalid": invalid,
            "sql_execution_accuracy": match,
            "sql_exact_match": float(
                " ".join(generated.lower().split()) == " ".join(record.gold_sql.lower().split())
            ),
        }
        detail = {
            "generated": generated,
            "gold": record.gold_sql,
            "order_sensitive": ordered,
            "gold_row_count": len(gold_rows),
            "predicted_row_count": len(predicted_rows or []),
        }
        return metrics, detail
