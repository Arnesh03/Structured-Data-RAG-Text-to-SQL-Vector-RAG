# Data

The dataset, what was wrong with it, and what the cleaning pipeline did about
it.

---

## Source

`healthcare_dataset.csv` — 55,500 synthetic hospital admissions, 15 columns,
covering 2019-05-08 to 2024-05-07. Synthetic throughout: no real patient data
is involved.

| Column | Notes |
|---|---|
| Name, Age, Gender, Blood Type | Patient demographics |
| Medical Condition | One of six chronic conditions |
| Date of Admission, Discharge Date | ISO dates |
| Doctor, Hospital | Free text, generated from name templates |
| Insurance Provider | One of five |
| Billing Amount | Total charge for the stay, USD |
| Room Number | 101–500 |
| Admission Type | Elective / Urgent / Emergency |
| Medication | One of five |
| Test Results | Normal / Abnormal / Inconclusive |

---

## What was wrong with it

The file is deliberately messy, which is why preprocessing is a real step
rather than a `read_csv`.

| Problem | Example | Rows affected |
|---|---|---|
| Scrambled letter case in names | `Bobby JacksOn`, `LesLie TErRy` | 55,467 |
| Trailing commas and dangling conjunctions in org names | `Hernandez Rogers and Vang,` | 13,519 |
| Byte-identical duplicate rows | — | 534 |
| Negative billing amounts | `-2008.49` | 106 |
| Floating-point tails on money | `18856.281305978155` | all |
| No patient key, stay length, or age band | — | all |

---

## The cleaning pipeline

Run by [`preprocess.py`](../preprocess.py). Every step is counted into
`data/preprocessing_report.json` and rendered in the app's **Data** tab.

**1. `trim_whitespace`** — collapse runs of whitespace, trim ends.

**2. `normalize_patient_name` / `normalize_doctor`** — title-case, preserving
name conventions rather than applying a naive `.title()`:

| Input | Output |
|---|---|
| `bOBby jacksON` | `Bobby Jackson` |
| `o'BRIEN` | `O'Brien` |
| `smith-JONES` | `Smith-Jones` |
| `mcDONALD` | `McDonald` |
| `maria DE la cruz` | `Maria de la Cruz` |

**3. `normalize_hospital`** — strip trailing punctuation and dangling
conjunctions. `Powers Miller, and Flores` → `Powers Miller and Flores`;
`Sons Rich and` → `Sons Rich`. Organisation names are *not* re-cased, since
that would break `PLC` and `Inc`.

**4. Categorical casing** — title-case the low-cardinality categoricals so
grouping is reliable. `insurance_provider` is deliberately excluded:
title-casing would turn `UnitedHealthcare` into `Unitedhealthcare`.

**5. `drop_duplicate_admissions`** — 534 rows identical across all 15 source
fields. Runs *after* name normalisation, so case-variant duplicates are caught
too.

**6. `drop_unparseable_dates`** — any row whose admission or discharge date
will not parse.

**7. `drop_impossible_stays`** — discharge before admission, or a stay longer
than `MAX_STAY_DAYS` (365).

**8. `repair_billing_amount`** — 106 negative charges. The source has no
credit-note concept, so these are read as sign errors on a charge rather than
refunds: the magnitude is kept and rounded to cents. *This is a judgement call
— if your reading is that they are refunds, drop them instead.*

**9. `drop_out_of_range_age`** — ages outside 0–120.

**10. `validate_categories`** — checks every categorical against its expected
vocabulary. **Reports only, coerces nothing**, so a genuinely new category
stays visible in the report instead of being silently mapped away.

**11. `derive_columns`** — seven new columns:
`length_of_stay_days`, `admission_year`, `admission_month`, `admission_dow`,
`age_group`, `billing_per_day`, plus `patient_id`.
Bill-per-day divides by `max(stay, 1)` — a same-day discharge still consumes a
day of care, and dividing by zero helps nobody.

**12. `assign_keys`** — `admission_id` is sequential. `patient_id` is a SHA-1
of name + gender + blood type, so the same person across multiple visits gets
the same id. The source has no patient key; this is a synthetic stand-in, not a
real identity resolution.

### Result

**55,500 rows in → 54,966 out (99.0% retained). 15 columns → 23.**

| Figure | Value |
|---|---|
| Unique patients | 48,896 |
| Hospitals | 39,876 |
| Physicians | 40,341 |
| Total billing | $1,404,174,862.05 |
| Median stay | 15 days |

---

## Schema

One wide `admissions` table. Text-to-SQL works best against a flat, commented
schema — every join the model doesn't have to guess is a query it doesn't get
wrong — so the derived columns are materialised rather than computed at query
time.

```sql
CREATE TABLE admissions (
    admission_id        TEXT PRIMARY KEY,  -- e.g. 'ADM-000001'
    patient_id          TEXT,              -- stable per patient across visits
    patient_name        TEXT,
    age                 INTEGER,
    age_group           TEXT,              -- Under 18 | 18-29 | 30-44 | 45-59 | 60-74 | 75+
    gender              TEXT,              -- Male | Female
    blood_type          TEXT,              -- A+ | A- | B+ | B- | AB+ | AB- | O+ | O-
    medical_condition   TEXT,              -- Arthritis | Asthma | Cancer | Diabetes | Hypertension | Obesity
    admission_date      TEXT,              -- ISO 'YYYY-MM-DD'
    discharge_date      TEXT,
    length_of_stay_days INTEGER,
    admission_year      INTEGER,
    admission_month     TEXT,              -- 'YYYY-MM'
    admission_dow       TEXT,
    doctor              TEXT,
    hospital            TEXT,
    insurance_provider  TEXT,              -- Aetna | Blue Cross | Cigna | Medicare | UnitedHealthcare
    billing_amount      REAL,              -- total charge, USD
    billing_per_day     REAL,
    room_number         INTEGER,
    admission_type      TEXT,              -- Elective | Urgent | Emergency
    medication          TEXT,              -- Aspirin | Ibuprofen | Lipitor | Paracetamol | Penicillin
    test_results        TEXT               -- Normal | Abnormal | Inconclusive
)
```

Indexed on `medical_condition`, `admission_type`, `admission_date`,
`admission_month`, `insurance_provider`, `hospital`, `patient_id`,
`test_results`.

**One row is one admission, not one patient.** Count admissions with
`COUNT(*)`, distinct patients with `COUNT(DISTINCT patient_id)`. The SQL prompt
says so explicitly, because it is the single easiest thing to get wrong here.

---

## The document corpus

Five documents, authored in [`policies_content.py`](../policies_content.py),
covering what the table cannot answer. 37 chunks across 9 PDF pages.

| Document | Covers |
|---|---|
| Patient Admission & Triage Policy | Admission types, ED triage levels, pre-admission testing, room assignment, observation status |
| Insurance, Billing & Financial Assistance Policy | The five providers, pre-authorisation, billing timelines, charity care, surprise-billing protections |
| Clinical Care Guidelines | Inpatient protocols for all six conditions, the five formulary medications, what a test result means |
| Discharge, Follow-Up & Readmission Policy | Discharge criteria, medication reconciliation, follow-up windows, readmission review |
| Patient Rights & FAQ | Visiting hours, medical records, HIPAA, advance directives, interpretation |

The corpus is written to be *answerable and checkable*: concrete numbers,
thresholds and timeframes throughout, so a retrieval failure is obvious rather
than plausible-sounding.

Text is ASCII-only — FPDF's built-in Helvetica is a latin-1 font.

---

## Rebuilding

```bash
make rebuild     # re-run preprocessing, SQLite and FAISS from the raw CSV
```

Or piecemeal:

```bash
python preprocess.py --force
python database.py --force
python vectorstore.py --force
```
