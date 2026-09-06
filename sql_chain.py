"""
Text-to-SQL pipeline.

Converts a natural language question into a SQLite query, validates that the
query is read-only, executes it, and turns the result back into prose.

The generated SQL is produced exactly once and both executed and displayed, so
what the UI shows is always the query that actually ran. Results come back as
columns plus rows rather than a formatted string, so the frontend can render a
real table or chart from the same data the model summarized.
"""
import re
import sqlite3
from functools import lru_cache

from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import DB_PATH, SQL_MAX_ROWS
from llm import get_llm


class UnsafeSQLError(ValueError):
    """Raised when the generated SQL is not a single read-only statement."""


# ── Prompts ───────────────────────────────────────────────────────────

SQL_PROMPT = ChatPromptTemplate.from_template("""\
You are a SQLite expert working with a hospital patient-admissions database.
Given a user question, write ONE syntactically correct SQLite SELECT query that
answers it.

Rules:
- Output ONLY the SQL query. No markdown fences, no explanation, no trailing prose.
- Use only the tables and columns in the schema below. Never invent columns.
- The query must be read-only: SELECT (or WITH ... SELECT) only.
- Unless the question asks for a specific larger number of rows, return at most
  {top_k} rows.
- One row is one ADMISSION, not one patient. Count admissions with COUNT(*) and
  distinct patients with COUNT(DISTINCT patient_id).
- Dates are TEXT in 'YYYY-MM-DD' form. `admission_month` ('YYYY-MM') and
  `admission_year` (INTEGER) are already materialized - prefer them over
  strftime() when grouping by period.
- `length_of_stay_days` is precomputed; do not recompute it from the dates.
- `billing_amount` is the total charge for the stay in USD. `billing_per_day`
  is that amount divided by the length of stay. Round monetary aggregates to 2
  decimal places.
- Categorical values are stored exactly as: gender Male/Female; admission_type
  Elective/Urgent/Emergency; test_results Normal/Abnormal/Inconclusive;
  medical_condition Arthritis/Asthma/Cancer/Diabetes/Hypertension/Obesity;
  insurance_provider Aetna/Blue Cross/Cigna/Medicare/UnitedHealthcare;
  medication Aspirin/Ibuprofen/Lipitor/Paracetamol/Penicillin.
- For a percentage or share, compute it in the query with
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM admissions), 2).
- Give aggregate columns readable aliases (e.g. AS total_billing).
- Order results in the way that makes the answer easy to read, usually by the
  aggregate descending.

Schema:
{schema}

Question: {question}

SQLQuery:""")

ANSWER_PROMPT = ChatPromptTemplate.from_template("""\
Given a user question, the SQL query that was run, and its result, write a clear
natural language answer.

Guidelines:
- Answer the question directly in the first sentence, with the key number in it.
- Format currency as $1,234.56, counts with thousands separators, and
  percentages with a % sign.
- If the result holds several rows, present them as a small markdown table.
- If the result is empty, say that no matching admissions were found.
- Do not mention SQL, the database, or the query itself in your answer.
- These are historical admission records, so describe what the data shows.
  Do not offer medical advice or interpret findings for an individual patient.

Question: {question}
SQL Query: {query}
SQL Result: {result}

Answer:""")


# ── SQL safety & cleanup ──────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\blimit\b\s+\d+", re.IGNORECASE)


def clean_sql(raw: str) -> str:
    """Strip markdown fences, `SQLQuery:` prefixes, and surrounding prose."""
    text = raw.strip()

    # ```sql ... ``` or ``` ... ```
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)

    text = re.sub(r"^\s*sql(?:query)?\s*:\s*", "", text, flags=re.IGNORECASE)

    # Drop any preamble before the first SELECT/WITH.
    start = re.search(r"\b(select|with)\b", text, re.IGNORECASE)
    if start:
        text = text[start.start():]

    return text.strip().rstrip(";").strip()


def validate_sql(query: str) -> str:
    """Return the query if it is a single read-only statement, else raise."""
    if not query:
        raise UnsafeSQLError("The model did not produce a SQL query.")

    if ";" in query:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")

    if not re.match(r"^\s*(select|with)\b", query, re.IGNORECASE):
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    forbidden = _FORBIDDEN.search(query)
    if forbidden:
        raise UnsafeSQLError(
            f"Refusing to run a query containing '{forbidden.group(0).upper()}'."
        )

    return query


def enforce_limit(query: str, max_rows: int = SQL_MAX_ROWS) -> str:
    """Append a LIMIT when the model didn't set one, capping result size."""
    if _LIMIT_RE.search(query):
        return query
    return f"{query} LIMIT {max_rows}"


def prepare_sql(raw: str, max_rows: int = SQL_MAX_ROWS) -> str:
    """Clean, validate, and row-limit a model-generated SQL string."""
    return enforce_limit(validate_sql(clean_sql(raw)), max_rows)


# ── Execution ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_db() -> SQLDatabase:
    """Cached SQLDatabase handle, used for schema introspection."""
    return SQLDatabase.from_uri(f"sqlite:///{DB_PATH}", sample_rows_in_table_info=3)


def run_query(query: str) -> tuple[list[str], list[list]]:
    """
    Execute a validated read-only query and return (columns, rows).

    Opens the database read-only at the connection level, so the safety check
    on the SQL text is a first line of defence rather than the only one.
    """
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cursor = conn.execute(query)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [list(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return columns, rows


def rows_as_text(columns: list[str], rows: list[list], limit: int = SQL_MAX_ROWS) -> str:
    """Render a result set compactly for the answer prompt."""
    if not rows:
        return "(no rows)"
    head = " | ".join(columns)
    body = "\n".join(" | ".join(str(v) for v in row) for row in rows[:limit])
    suffix = f"\n... ({len(rows) - limit} more rows)" if len(rows) > limit else ""
    return f"{head}\n{body}{suffix}"


# ── Chain ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_sql_generator():
    """Chain: question -> raw SQL text."""
    return SQL_PROMPT | get_llm() | StrOutputParser()


@lru_cache(maxsize=1)
def get_answer_chain():
    """Chain: (question, query, result) -> natural language answer."""
    return ANSWER_PROMPT | get_llm() | StrOutputParser()


def generate_sql(question: str) -> str:
    """Generate, clean, validate, and limit the SQL for a question."""
    raw = get_sql_generator().invoke({
        "question": question,
        "schema": get_db().get_table_info(),
        "top_k": SQL_MAX_ROWS,
    })
    return prepare_sql(raw)


def query_sql(question: str) -> dict:
    """
    Run a natural language question through the Text-to-SQL pipeline.

    Returns a dict with keys: 'answer', 'sql_query', 'columns', 'rows',
    'row_count', 'route'.
    """
    sql_query = generate_sql(question)
    columns, rows = run_query(sql_query)

    answer = get_answer_chain().invoke({
        "question": question,
        "query": sql_query,
        "result": rows_as_text(columns, rows),
    })

    return {
        "answer": answer,
        "sql_query": sql_query,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "route": "sql",
    }
