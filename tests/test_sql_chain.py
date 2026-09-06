"""SQL cleaning, the read-only guard, and live execution."""
import pytest

from sql_chain import (
    UnsafeSQLError,
    clean_sql,
    enforce_limit,
    generate_sql,
    prepare_sql,
    query_sql,
    rows_as_text,
    run_query,
    validate_sql,
)


@pytest.mark.parametrize("raw,expected", [
    ("```sql\nSELECT 1 FROM admissions;\n```", "SELECT 1 FROM admissions"),
    ("```\nSELECT 1 FROM admissions\n```", "SELECT 1 FROM admissions"),
    ("SQLQuery: SELECT 1 FROM admissions", "SELECT 1 FROM admissions"),
    ("Here you go:\nSELECT 1 FROM admissions", "SELECT 1 FROM admissions"),
    ("  SELECT 1 FROM admissions ;  ", "SELECT 1 FROM admissions"),
])
def test_clean_sql_strips_noise(raw, expected):
    assert clean_sql(raw) == expected


@pytest.mark.parametrize("query", [
    "DROP TABLE admissions",
    "DELETE FROM admissions",
    "UPDATE admissions SET age = 0",
    "INSERT INTO admissions VALUES (1)",
    "SELECT 1; DROP TABLE admissions",
    "ATTACH DATABASE 'x' AS y",
    "",
])
def test_write_statements_are_rejected(query):
    with pytest.raises(UnsafeSQLError):
        validate_sql(clean_sql(query))


@pytest.mark.parametrize("query", [
    "SELECT COUNT(*) FROM admissions",
    "WITH t AS (SELECT 1 AS n) SELECT n FROM t",
])
def test_read_only_statements_pass(query):
    assert validate_sql(query) == query


def test_limit_is_added_when_missing():
    assert enforce_limit("SELECT * FROM admissions", 5).endswith("LIMIT 5")


def test_existing_limit_is_preserved():
    assert enforce_limit("SELECT * FROM admissions LIMIT 3", 20).endswith("LIMIT 3")


def test_prepare_sql_cleans_validates_and_limits():
    assert prepare_sql("```sql\nSELECT * FROM admissions\n```", 7) == (
        "SELECT * FROM admissions LIMIT 7"
    )


def test_run_query_returns_columns_and_rows():
    columns, rows = run_query(
        "SELECT medical_condition, COUNT(*) AS n FROM admissions "
        "GROUP BY 1 ORDER BY n DESC LIMIT 3"
    )
    assert columns == ["medical_condition", "n"]
    assert len(rows) == 3
    assert all(isinstance(r[1], int) for r in rows)


def test_the_read_only_connection_refuses_writes():
    import sqlite3

    with pytest.raises(sqlite3.OperationalError):
        run_query("CREATE TABLE t (x INT)")


def test_rows_as_text_renders_a_compact_table():
    text = rows_as_text(["a", "b"], [[1, 2], [3, 4]])
    assert text.splitlines() == ["a | b", "1 | 2", "3 | 4"]


def test_rows_as_text_handles_an_empty_result():
    assert rows_as_text(["a"], []) == "(no rows)"


def test_generated_sql_executes_against_the_real_database(fake_llm):
    fake_llm(
        "```sql\nSELECT ROUND(AVG(billing_amount), 2) AS avg_billing FROM admissions\n```"
    )
    sql = generate_sql("What is the average billing amount?")
    assert "AVG(billing_amount)" in sql and "LIMIT" in sql
    columns, rows = run_query(sql)
    assert columns == ["avg_billing"] and rows[0][0] > 0


def test_query_sql_returns_answer_sql_and_structured_rows(fake_llm):
    fake_llm(
        "SELECT COUNT(*) AS n FROM admissions",
        "There are 54,966 admissions in total.",
    )
    result = query_sql("How many admissions are there?")
    assert result["route"] == "sql"
    assert result["sql_query"].startswith("SELECT COUNT(*)")
    assert "54,966" in result["answer"]
    assert result["columns"] == ["n"]
    assert result["rows"][0][0] > 0
    assert result["row_count"] == 1


def test_unsafe_generated_sql_raises(fake_llm):
    fake_llm("DROP TABLE admissions")
    with pytest.raises(UnsafeSQLError):
        generate_sql("delete everything")
