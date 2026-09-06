"""The cleaning pipeline: text normalization, row drops, derived columns."""
import pandas as pd
import pytest

from preprocess import (
    AGE_LABELS,
    RAW_COLUMNS,
    clean_org_name,
    clean_person_name,
    make_patient_id,
    preprocess,
)


@pytest.mark.parametrize("raw,expected", [
    ("Bobby JacksOn", "Bobby Jackson"),
    ("LesLie TErRy", "Leslie Terry"),
    ("andrEw waTtS", "Andrew Watts"),
    ("  danny   sMITH  ", "Danny Smith"),
    ("o'BRIEN", "O'Brien"),
    ("smith-JONES", "Smith-Jones"),
    ("mcDONALD", "McDonald"),
    ("maria DE la cruz", "Maria de la Cruz"),
])
def test_person_names_are_normalized(raw, expected):
    assert clean_person_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Hernandez Rogers and Vang,", "Hernandez Rogers and Vang"),
    ("Powers Miller, and Flores", "Powers Miller and Flores"),
    ("Sons Rich and", "Sons Rich"),
    ("  White-White  ", "White-White"),
    ("Kim Inc", "Kim Inc"),
])
def test_organization_names_are_tidied(raw, expected):
    assert clean_org_name(raw) == expected


def test_patient_id_is_stable_across_visits():
    a = make_patient_id("Bobby Jackson", "Male", "B-")
    b = make_patient_id("bobby jackson", "male", "b-")
    assert a == b
    assert a != make_patient_id("Bobby Jackson", "Female", "B-")


# ── A tiny raw frame exercising every cleaning branch ─────────────────

def _raw_row(**overrides) -> dict:
    row = {
        "Name": "bOBby jacksON",
        "Age": 30,
        "Gender": "Male",
        "Blood Type": "B-",
        "Medical Condition": "Cancer",
        "Date of Admission": "2024-01-31",
        "Doctor": "matthew SMITH",
        "Hospital": "Sons and Miller,",
        "Insurance Provider": "Blue Cross",
        "Billing Amount": 18856.281305978155,
        "Room Number": 328,
        "Admission Type": "Urgent",
        "Discharge Date": "2024-02-02",
        "Medication": "Paracetamol",
        "Test Results": "Normal",
    }
    row.update(overrides)
    return row


@pytest.fixture
def raw() -> pd.DataFrame:
    return pd.DataFrame([
        _raw_row(),
        _raw_row(),                                      # exact duplicate
        _raw_row(Name="jane DOE", **{"Billing Amount": -500.0}),  # sign error
        _raw_row(Name="john ROE", **{"Discharge Date": "2023-01-01"}),  # before admission
        _raw_row(Name="amy POE", Age=200),               # impossible age
    ], columns=RAW_COLUMNS)


def test_duplicates_and_impossible_rows_are_dropped(raw):
    df, report = preprocess(raw)
    assert report["rows_in"] == 5
    # One duplicate, one reversed date range, one impossible age.
    assert report["rows_out"] == 2
    assert report["rows_dropped"] == 3


def test_negative_billing_becomes_a_positive_charge(raw):
    df, _ = preprocess(raw)
    assert (df["billing_amount"] >= 0).all()
    assert 500.0 in set(df["billing_amount"])


def test_billing_is_rounded_to_cents(raw):
    df, _ = preprocess(raw)
    assert df["billing_amount"].tolist() == [
        round(v, 2) for v in df["billing_amount"]
    ]


def test_derived_columns_are_present_and_correct(raw):
    df, _ = preprocess(raw)
    row = df[df["patient_name"] == "Bobby Jackson"].iloc[0]
    assert row["length_of_stay_days"] == 2
    assert row["admission_month"] == "2024-01"
    assert row["admission_year"] == 2024
    assert row["age_group"] in AGE_LABELS
    assert row["billing_per_day"] == pytest.approx(18856.28 / 2, abs=0.01)
    assert row["hospital"] == "Sons and Miller"
    assert row["doctor"] == "Matthew Smith"


def test_admission_ids_are_unique_and_sequential(raw):
    df, _ = preprocess(raw)
    assert df["admission_id"].is_unique
    assert df["admission_id"].iloc[0] == "ADM-000001"


def test_report_records_every_step(raw):
    _, report = preprocess(raw)
    steps = {s["step"] for s in report["steps"]}
    assert {
        "trim_whitespace", "normalize_patient_name", "normalize_hospital",
        "drop_duplicate_admissions", "drop_impossible_stays",
        "repair_billing_amount", "derive_columns", "assign_keys",
    } <= steps
    assert all(s["detail"] for s in report["steps"])
