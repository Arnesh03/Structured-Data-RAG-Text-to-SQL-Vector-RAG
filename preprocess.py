"""
Healthcare dataset preprocessing.

Turns the raw Kaggle-style `healthcare_dataset.csv` into an analysis-ready
table. The raw file is synthetic but deliberately messy: names arrive in
scrambled case ("Bobby JacksOn"), hospital names carry trailing commas,
billing amounts have floating-point tails and a handful of negative values,
and a few hundred rows are exact duplicates.

Every transformation is counted, so `python preprocess.py` prints — and
`data/preprocessing_report.json` records — exactly what changed and why.

Run standalone:  python preprocess.py [--force]
"""
import argparse
import hashlib
import json
import re
from datetime import datetime

import pandas as pd

from config import CLEAN_CSV_PATH, MAX_STAY_DAYS, RAW_CSV_PATH, REPORT_PATH

# ── Column names ──────────────────────────────────────────────────────

RAW_COLUMNS = [
    "Name", "Age", "Gender", "Blood Type", "Medical Condition",
    "Date of Admission", "Doctor", "Hospital", "Insurance Provider",
    "Billing Amount", "Room Number", "Admission Type", "Discharge Date",
    "Medication", "Test Results",
]

COLUMN_RENAMES = {
    "Name": "patient_name",
    "Age": "age",
    "Gender": "gender",
    "Blood Type": "blood_type",
    "Medical Condition": "medical_condition",
    "Date of Admission": "admission_date",
    "Doctor": "doctor",
    "Hospital": "hospital",
    "Insurance Provider": "insurance_provider",
    "Billing Amount": "billing_amount",
    "Room Number": "room_number",
    "Admission Type": "admission_type",
    "Discharge Date": "discharge_date",
    "Medication": "medication",
    "Test Results": "test_results",
}

TEXT_COLUMNS = [
    "patient_name", "gender", "blood_type", "medical_condition", "doctor",
    "hospital", "insurance_provider", "admission_type", "medication",
    "test_results",
]

# ── Controlled vocabularies (used to validate, not to coerce) ─────────

VALID_GENDERS = {"Male", "Female"}
VALID_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_TEST_RESULTS = {"Normal", "Abnormal", "Inconclusive"}
VALID_ADMISSION_TYPES = {"Elective", "Urgent", "Emergency"}

AGE_BINS = [0, 18, 30, 45, 60, 75, 200]
AGE_LABELS = ["Under 18", "18-29", "30-44", "45-59", "60-74", "75+"]

# Particles that stay lowercase inside a multi-word name.
_NAME_PARTICLES = {"de", "del", "der", "van", "von", "la", "le", "da", "di", "du"}
_MC_MAC = re.compile(r"^(mc)([a-z])(.*)$", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════
# Text cleaning
# ═══════════════════════════════════════════════════════════════════════

def _capitalize_token(token: str, first: bool) -> str:
    """Title-case one whitespace-delimited token, respecting name conventions."""
    if not token:
        return token

    # Recurse through hyphens and apostrophes: "smith-jones" -> "Smith-Jones",
    # "o'brien" -> "O'Brien".
    for sep in ("-", "'", "’"):
        if sep in token:
            parts = token.split(sep)
            return sep.join(
                _capitalize_token(p, first and i == 0) for i, p in enumerate(parts)
            )

    lowered = token.lower()
    if not first and lowered in _NAME_PARTICLES:
        return lowered

    mc = _MC_MAC.match(lowered)
    if mc and len(lowered) > 3:
        return f"Mc{mc.group(2).upper()}{mc.group(3)}"

    return lowered[0].upper() + lowered[1:]


def clean_person_name(value: str) -> str:
    """
    Normalize a scrambled-case person name.

    'Bobby JacksOn' -> 'Bobby Jackson';  'dANNY o\'sMITH' -> 'Danny O\'Smith'.
    """
    if not isinstance(value, str):
        return value
    tokens = re.sub(r"\s+", " ", value).strip().split(" ")
    return " ".join(
        _capitalize_token(tok, first=(i == 0)) for i, tok in enumerate(tokens)
    )


def clean_org_name(value: str) -> str:
    """
    Tidy an organization name without re-casing it.

    The raw hospital names are generated from company-name templates and come
    out with stray commas and dangling conjunctions:
      'Hernandez Rogers and Vang,'  -> 'Hernandez Rogers and Vang'
      'Powers Miller, and Flores'   -> 'Powers Miller and Flores'
      'Sons Rich and'               -> 'Sons Rich'
    """
    if not isinstance(value, str):
        return value
    text = re.sub(r"\s+", " ", value).strip()
    text = re.sub(r",(\s*and\b)", r"\1", text, flags=re.IGNORECASE)  # 'X, and Y'
    text = text.strip(" ,.-")
    text = re.sub(r"\s+(and|&)$", "", text, flags=re.IGNORECASE)     # dangling 'and'
    return text.strip(" ,.-")


def make_patient_id(name: str, gender: str, blood_type: str) -> str:
    """
    Stable synthetic patient id.

    The source has no patient key, so identity is derived from the fields that
    don't change between visits. Same person, multiple admissions -> same id.
    """
    seed = f"{name.lower()}|{gender.lower()}|{blood_type.upper()}"
    return "PT-" + hashlib.sha1(seed.encode()).hexdigest()[:10].upper()


# ═══════════════════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════════════════

def load_raw(path=RAW_CSV_PATH) -> pd.DataFrame:
    """Read the raw CSV and check the expected columns are present."""
    if not path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at {path}.\n"
            "Place healthcare_dataset.csv in the project root, or set RAW_CSV_PATH."
        )
    df = pd.read_csv(path)
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Raw dataset is missing columns: {missing}")
    return df[RAW_COLUMNS]


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean the raw frame and return `(clean_df, report)`.

    The report counts every row dropped and every value rewritten, so the
    cleaning is auditable rather than silent.
    """
    report: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows_in": int(len(df)),
        "steps": [],
    }

    def step(name: str, detail: str, **counts) -> None:
        report["steps"].append({"step": name, "detail": detail, **counts})

    df = df.rename(columns=COLUMN_RENAMES).copy()

    # 1. Trim stray whitespace from every text column.
    whitespace_fixed = 0
    for col in TEXT_COLUMNS:
        stripped = df[col].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        whitespace_fixed += int((stripped != df[col]).sum())
        df[col] = stripped
    step("trim_whitespace", "Collapsed runs of whitespace and trimmed ends.",
         values_changed=whitespace_fixed)

    # 2. Normalize scrambled-case person names.
    for col in ("patient_name", "doctor"):
        cleaned = df[col].map(clean_person_name)
        step(f"normalize_{col}", f"Title-cased {col.replace('_', ' ')} values.",
             values_changed=int((cleaned != df[col]).sum()))
        df[col] = cleaned

    # 3. Tidy hospital names (trailing commas, dangling conjunctions).
    cleaned_hospital = df["hospital"].map(clean_org_name)
    step("normalize_hospital", "Removed trailing commas and dangling conjunctions.",
         values_changed=int((cleaned_hospital != df["hospital"]).sum()))
    df["hospital"] = cleaned_hospital

    # 4. Title-case the low-cardinality categoricals so grouping is reliable.
    #    insurance_provider is left alone: title-casing would turn
    #    "UnitedHealthcare" into "Unitedhealthcare".
    for col in ("gender", "medical_condition", "admission_type", "medication",
                "test_results"):
        df[col] = df[col].str.title()
    df["blood_type"] = df["blood_type"].str.upper().str.replace(" ", "", regex=False)

    # 5. Drop exact duplicate admissions.
    before = len(df)
    df = df.drop_duplicates(subset=list(COLUMN_RENAMES.values()))
    step("drop_duplicate_admissions",
         "Removed rows identical across all 15 source fields.",
         rows_dropped=before - len(df))

    # 6. Parse dates; drop anything unparseable.
    df["admission_date"] = pd.to_datetime(df["admission_date"], errors="coerce")
    df["discharge_date"] = pd.to_datetime(df["discharge_date"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["admission_date", "discharge_date"])
    step("drop_unparseable_dates", "Removed rows with an invalid admission or discharge date.",
         rows_dropped=before - len(df))

    # 7. Length of stay, and the rows whose dates make no sense.
    stay = (df["discharge_date"] - df["admission_date"]).dt.days
    invalid = (stay < 0) | (stay > MAX_STAY_DAYS)
    step("drop_impossible_stays",
         f"Removed discharge-before-admission rows and stays over {MAX_STAY_DAYS} days.",
         rows_dropped=int(invalid.sum()))
    df = df[~invalid].copy()
    df["length_of_stay_days"] = (df["discharge_date"] - df["admission_date"]).dt.days

    # 8. Billing: negatives are sign errors on a charge, not refunds — the
    #    source has no credit-note concept — so take the magnitude and round.
    negatives = int((df["billing_amount"] < 0).sum())
    df["billing_amount"] = df["billing_amount"].abs().round(2)
    step("repair_billing_amount",
         "Took the magnitude of negative charges and rounded to 2 decimals.",
         values_changed=negatives)

    # 9. Range-check age; drop the impossible ones.
    before = len(df)
    df = df[df["age"].between(0, 120)]
    step("drop_out_of_range_age", "Removed ages outside 0-120.", rows_dropped=before - len(df))

    # 10. Flag any category outside the expected vocabulary (report only —
    #     nothing is coerced, so a genuinely new category stays visible).
    unexpected = {
        "gender": sorted(set(df["gender"]) - VALID_GENDERS),
        "blood_type": sorted(set(df["blood_type"]) - VALID_BLOOD_TYPES),
        "test_results": sorted(set(df["test_results"]) - VALID_TEST_RESULTS),
        "admission_type": sorted(set(df["admission_type"]) - VALID_ADMISSION_TYPES),
    }
    step("validate_categories", "Checked categoricals against the expected vocabulary.",
         unexpected_values={k: v for k, v in unexpected.items() if v})

    # 11. Derived analytics columns.
    df["admission_year"] = df["admission_date"].dt.year.astype(int)
    df["admission_month"] = df["admission_date"].dt.strftime("%Y-%m")
    df["admission_dow"] = df["admission_date"].dt.day_name()
    df["age_group"] = pd.cut(df["age"], bins=AGE_BINS, labels=AGE_LABELS,
                             right=False, include_lowest=True).astype(str)
    # A same-day discharge still consumes a day of care, so bill-per-day
    # divides by at least 1 rather than by zero.
    df["billing_per_day"] = (
        df["billing_amount"] / df["length_of_stay_days"].clip(lower=1)
    ).round(2)
    step("derive_columns",
         "Added length_of_stay_days, admission_year/month/dow, age_group, billing_per_day.",
         columns_added=7)

    # 12. Keys.
    df["patient_id"] = [
        make_patient_id(n, g, b)
        for n, g, b in zip(df["patient_name"], df["gender"], df["blood_type"])
    ]
    df = df.sort_values(["admission_date", "patient_name"]).reset_index(drop=True)
    df.insert(0, "admission_id", [f"ADM-{i:06d}" for i in range(1, len(df) + 1)])
    step("assign_keys",
         "Assigned admission_id and a name/gender/blood-type-derived patient_id.",
         unique_patients=int(df["patient_id"].nunique()))

    # 13. Final column order and date formatting.
    df["admission_date"] = df["admission_date"].dt.strftime("%Y-%m-%d")
    df["discharge_date"] = df["discharge_date"].dt.strftime("%Y-%m-%d")
    df = df[[
        "admission_id", "patient_id", "patient_name", "age", "age_group", "gender",
        "blood_type", "medical_condition", "admission_date", "discharge_date",
        "length_of_stay_days", "admission_year", "admission_month", "admission_dow",
        "doctor", "hospital", "insurance_provider", "billing_amount",
        "billing_per_day", "room_number", "admission_type", "medication",
        "test_results",
    ]]

    report["rows_out"] = int(len(df))
    report["rows_dropped"] = report["rows_in"] - report["rows_out"]
    report["columns_out"] = list(df.columns)
    report["summary"] = {
        "unique_patients": int(df["patient_id"].nunique()),
        "unique_hospitals": int(df["hospital"].nunique()),
        "unique_doctors": int(df["doctor"].nunique()),
        "date_range": [df["admission_date"].min(), df["admission_date"].max()],
        "total_billing": round(float(df["billing_amount"].sum()), 2),
        "median_stay_days": float(df["length_of_stay_days"].median()),
    }
    return df, report


def clean_data_is_ready() -> bool:
    """True when a cleaned CSV is already on disk."""
    return CLEAN_CSV_PATH.exists()


def run(force: bool = False) -> pd.DataFrame:
    """Preprocess the raw CSV and write the clean CSV plus the audit report."""
    if clean_data_is_ready() and not force:
        print("  Cleaned dataset already exists - skipping (use --force to rebuild).")
        return pd.read_csv(CLEAN_CSV_PATH)

    print("Preprocessing healthcare dataset...")
    raw = load_raw()
    df, report = preprocess(raw)

    df.to_csv(CLEAN_CSV_PATH, index=False)
    REPORT_PATH.write_text(json.dumps(report, indent=2))

    for s in report["steps"]:
        counts = ", ".join(
            f"{k}={v}" for k, v in s.items()
            if k not in ("step", "detail") and v not in (0, {}, [])
        )
        if counts:
            print(f"  {s['step']}: {counts}")
    print(f"  {report['rows_in']} rows in -> {report['rows_out']} rows out "
          f"({report['rows_dropped']} dropped)")
    print(f"  Saved {CLEAN_CSV_PATH}")
    print(f"  Saved {REPORT_PATH}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean the raw healthcare dataset.")
    parser.add_argument("--force", action="store_true", help="rebuild even if it exists")
    run(force=parser.parse_args().force)
