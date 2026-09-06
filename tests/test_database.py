"""The SQLite schema built from the cleaned admissions."""
import sqlite3

import pandas as pd
import pytest

from config import CLEAN_CSV_PATH, DB_PATH
from database import COLUMNS, TABLE_NAME, database_is_ready

EXPECTED_COLUMNS = set(COLUMNS)


def test_database_is_built_and_populated():
    assert database_is_ready(), "run `python cli.py --setup` first"


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield connection
    connection.close()


def test_table_has_expected_columns(conn):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE_NAME})")}
    assert cols == EXPECTED_COLUMNS


def test_row_count_matches_the_clean_csv(conn):
    rows = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    assert rows == len(pd.read_csv(CLEAN_CSV_PATH))


def test_indexes_exist_for_the_common_group_by_columns(conn):
    indexed = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (TABLE_NAME,),
        )
    }
    assert {"idx_adm_condition", "idx_adm_month", "idx_adm_insurer"} <= indexed


def test_no_negative_billing_or_impossible_stays(conn):
    bad = conn.execute(
        f"SELECT COUNT(*) FROM {TABLE_NAME} "
        "WHERE billing_amount < 0 OR length_of_stay_days < 0"
    ).fetchone()[0]
    assert bad == 0


def test_categoricals_use_the_expected_vocabulary(conn):
    checks = {
        "gender": {"Male", "Female"},
        "admission_type": {"Elective", "Urgent", "Emergency"},
        "test_results": {"Normal", "Abnormal", "Inconclusive"},
        "medical_condition": {
            "Arthritis", "Asthma", "Cancer", "Diabetes", "Hypertension", "Obesity",
        },
    }
    for column, allowed in checks.items():
        found = {r[0] for r in conn.execute(
            f"SELECT DISTINCT {column} FROM {TABLE_NAME}"
        )}
        assert found <= allowed, f"{column} has unexpected values: {found - allowed}"
