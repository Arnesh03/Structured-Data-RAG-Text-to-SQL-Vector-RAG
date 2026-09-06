"""
Database setup: loads the cleaned healthcare admissions into SQLite.

The schema is a single wide `admissions` table. Text-to-SQL works best against
a flat, well-commented schema — every join the model doesn't have to guess is
a query it doesn't get wrong — so the derived columns from preprocessing
(length of stay, age group, admission month) are materialized as real columns.

Run standalone:  python database.py [--force]
"""
import argparse
import sqlite3

import pandas as pd

from config import CLEAN_CSV_PATH, DB_PATH
from preprocess import run as run_preprocessing

TABLE_NAME = "admissions"

CREATE_TABLE_SQL = """
    CREATE TABLE admissions (
        admission_id        TEXT PRIMARY KEY,  -- e.g. 'ADM-000001'
        patient_id          TEXT,              -- stable per patient across visits
        patient_name        TEXT,
        age                 INTEGER,           -- years at admission
        age_group           TEXT,              -- Under 18 | 18-29 | 30-44 | 45-59 | 60-74 | 75+
        gender              TEXT,              -- Male | Female
        blood_type          TEXT,              -- A+ | A- | B+ | B- | AB+ | AB- | O+ | O-
        medical_condition   TEXT,              -- Arthritis | Asthma | Cancer | Diabetes | Hypertension | Obesity
        admission_date      TEXT,              -- ISO date 'YYYY-MM-DD'
        discharge_date      TEXT,              -- ISO date 'YYYY-MM-DD'
        length_of_stay_days INTEGER,           -- discharge_date - admission_date
        admission_year      INTEGER,           -- e.g. 2023
        admission_month     TEXT,              -- 'YYYY-MM'
        admission_dow       TEXT,              -- weekday name of admission
        doctor              TEXT,              -- attending physician
        hospital            TEXT,
        insurance_provider  TEXT,              -- Aetna | Blue Cross | Cigna | Medicare | UnitedHealthcare
        billing_amount      REAL,              -- total charge for the stay, USD
        billing_per_day     REAL,              -- billing_amount / length_of_stay_days, USD
        room_number         INTEGER,
        admission_type      TEXT,              -- Elective | Urgent | Emergency
        medication          TEXT,              -- Aspirin | Ibuprofen | Lipitor | Paracetamol | Penicillin
        test_results        TEXT               -- Normal | Abnormal | Inconclusive
    )
"""

INDEX_SQL = [
    "CREATE INDEX idx_adm_condition ON admissions(medical_condition)",
    "CREATE INDEX idx_adm_type ON admissions(admission_type)",
    "CREATE INDEX idx_adm_date ON admissions(admission_date)",
    "CREATE INDEX idx_adm_month ON admissions(admission_month)",
    "CREATE INDEX idx_adm_insurer ON admissions(insurance_provider)",
    "CREATE INDEX idx_adm_hospital ON admissions(hospital)",
    "CREATE INDEX idx_adm_patient ON admissions(patient_id)",
    "CREATE INDEX idx_adm_results ON admissions(test_results)",
]

COLUMNS = [
    "admission_id", "patient_id", "patient_name", "age", "age_group", "gender",
    "blood_type", "medical_condition", "admission_date", "discharge_date",
    "length_of_stay_days", "admission_year", "admission_month", "admission_dow",
    "doctor", "hospital", "insurance_provider", "billing_amount",
    "billing_per_day", "room_number", "admission_type", "medication",
    "test_results",
]


def load_into_sqlite(df: pd.DataFrame) -> int:
    """Create the SQLite database and insert admissions. Returns the row count."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        cursor.execute(CREATE_TABLE_SQL)
        cursor.executemany(
            f"INSERT INTO {TABLE_NAME} VALUES ({', '.join('?' * len(COLUMNS))})",
            df[COLUMNS].itertuples(index=False, name=None),
        )
        for stmt in INDEX_SQL:
            cursor.execute(stmt)
        conn.commit()
        count = cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    finally:
        conn.close()

    print(f"  Loaded {count:,} admissions into SQLite at {DB_PATH}")
    return count


def database_is_ready() -> bool:
    """True when the DB file exists and holds a populated `admissions` table."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (TABLE_NAME,),
            ).fetchone()
            if row is None:
                return False
            return conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0] > 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def setup_database(force: bool = False) -> None:
    """Preprocess the raw CSV if needed, then load it into SQLite."""
    if database_is_ready() and not force:
        print("  Database already exists - skipping (use force=True to rebuild).")
        return

    df = run_preprocessing(force=force) if force or not CLEAN_CSV_PATH.exists() \
        else pd.read_csv(CLEAN_CSV_PATH)

    print("Building healthcare database...")
    load_into_sqlite(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the healthcare SQLite database.")
    parser.add_argument("--force", action="store_true", help="rebuild even if it exists")
    setup_database(force=parser.parse_args().force)
