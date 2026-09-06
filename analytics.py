"""
Dashboard analytics.

Pure SQL aggregations over the admissions table, with no LLM in the path. The
chat pipeline answers open-ended questions; this module answers the same fixed
set of questions every time the dashboard loads, which makes it fast enough to
serve on every page view and cheap enough to cache.
"""
import json
import sqlite3
from functools import lru_cache

from config import DB_PATH, REPORT_PATH


def _connect() -> sqlite3.Connection:
    """Open the admissions database read-only."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(r) for r in conn.execute(sql)]


def _one(conn: sqlite3.Connection, sql: str) -> dict:
    row = conn.execute(sql).fetchone()
    return dict(row) if row else {}


@lru_cache(maxsize=1)
def dashboard() -> dict:
    """
    Every figure the analytics dashboard renders, in one round trip.

    Cached because the underlying table is immutable once built; call
    `dashboard.cache_clear()` after a rebuild.
    """
    conn = _connect()
    try:
        kpis = _one(conn, """
            SELECT
                COUNT(*)                                  AS total_admissions,
                COUNT(DISTINCT patient_id)                AS unique_patients,
                COUNT(DISTINCT hospital)                  AS hospitals,
                COUNT(DISTINCT doctor)                    AS doctors,
                ROUND(SUM(billing_amount), 2)             AS total_billing,
                ROUND(AVG(billing_amount), 2)             AS avg_billing,
                ROUND(AVG(length_of_stay_days), 1)        AS avg_stay_days,
                ROUND(AVG(age), 1)                        AS avg_age,
                MIN(admission_date)                       AS first_admission,
                MAX(admission_date)                       AS last_admission
            FROM admissions
        """)
        kpis["emergency_share"] = _one(conn, """
            SELECT ROUND(100.0 * SUM(admission_type = 'Emergency') / COUNT(*), 1) AS pct
            FROM admissions
        """).get("pct")
        kpis["abnormal_share"] = _one(conn, """
            SELECT ROUND(100.0 * SUM(test_results = 'Abnormal') / COUNT(*), 1) AS pct
            FROM admissions
        """).get("pct")

        return {
            "kpis": kpis,
            "by_condition": _rows(conn, """
                SELECT medical_condition AS name,
                       COUNT(*)                           AS admissions,
                       ROUND(AVG(billing_amount), 2)      AS avg_billing,
                       ROUND(AVG(length_of_stay_days), 1) AS avg_stay,
                       ROUND(SUM(billing_amount), 2)      AS total_billing
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "by_month": _rows(conn, """
                SELECT admission_month AS name,
                       COUNT(*)                      AS admissions,
                       ROUND(SUM(billing_amount), 2) AS billing
                FROM admissions GROUP BY 1 ORDER BY 1
            """),
            "by_admission_type": _rows(conn, """
                SELECT admission_type AS name,
                       COUNT(*)                           AS admissions,
                       ROUND(AVG(length_of_stay_days), 1) AS avg_stay
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "by_insurance": _rows(conn, """
                SELECT insurance_provider AS name,
                       COUNT(*)                      AS admissions,
                       ROUND(AVG(billing_amount), 2) AS avg_billing,
                       ROUND(SUM(billing_amount), 2) AS total_billing
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "by_age_group": _rows(conn, """
                SELECT age_group AS name,
                       COUNT(*)                      AS admissions,
                       ROUND(AVG(billing_amount), 2) AS avg_billing
                FROM admissions GROUP BY 1
                ORDER BY MIN(age)
            """),
            "by_test_result": _rows(conn, """
                SELECT test_results AS name, COUNT(*) AS admissions
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "by_gender": _rows(conn, """
                SELECT gender AS name, COUNT(*) AS admissions
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "by_medication": _rows(conn, """
                SELECT medication AS name, COUNT(*) AS admissions
                FROM admissions GROUP BY 1 ORDER BY admissions DESC
            """),
            "stay_by_condition": _rows(conn, """
                SELECT medical_condition AS name,
                       ROUND(AVG(length_of_stay_days), 2) AS avg_stay,
                       MIN(length_of_stay_days)           AS min_stay,
                       MAX(length_of_stay_days)           AS max_stay
                FROM admissions GROUP BY 1 ORDER BY avg_stay DESC
            """),
            "top_hospitals": _rows(conn, """
                SELECT hospital AS name,
                       COUNT(*)                      AS admissions,
                       ROUND(SUM(billing_amount), 2) AS total_billing
                FROM admissions GROUP BY 1 ORDER BY admissions DESC, name LIMIT 10
            """),
        }
    finally:
        conn.close()


@lru_cache(maxsize=1)
def preprocessing_report() -> dict:
    """The audit trail written by `preprocess.py`, or an empty dict if absent."""
    if not REPORT_PATH.exists():
        return {}
    return json.loads(REPORT_PATH.read_text())


@lru_cache(maxsize=1)
def schema_info() -> list[dict]:
    """Column names, types, and the comment describing each one."""
    import re

    from database import CREATE_TABLE_SQL

    columns = []
    for line in CREATE_TABLE_SQL.splitlines():
        match = re.match(
            r"\s*(\w+)\s+(TEXT|INTEGER|REAL)\b[^-]*(?:--\s*(.*))?$", line.strip()
        )
        if match:
            columns.append({
                "name": match.group(1),
                "type": match.group(2),
                "description": (match.group(3) or "").strip(),
            })
    return columns


def clear_caches() -> None:
    """Drop cached aggregates after the database is rebuilt."""
    dashboard.cache_clear()
    preprocessing_report.cache_clear()
    schema_info.cache_clear()


if __name__ == "__main__":
    print(json.dumps(dashboard(), indent=2)[:2000])
