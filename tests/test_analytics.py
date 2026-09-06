"""Dashboard aggregations, the schema view, and the preprocessing report."""
import analytics


def test_kpis_are_populated():
    kpis = analytics.dashboard()["kpis"]
    assert kpis["total_admissions"] > 0
    assert 0 < kpis["unique_patients"] <= kpis["total_admissions"]
    assert kpis["avg_billing"] > 0
    assert kpis["avg_stay_days"] > 0
    assert kpis["first_admission"] < kpis["last_admission"]
    assert 0 <= kpis["emergency_share"] <= 100


def test_every_series_is_named_and_counted():
    data = analytics.dashboard()
    series_keys = [k for k in data if k != "kpis"]
    assert series_keys
    for key in series_keys:
        rows = data[key]
        assert rows, f"{key} is empty"
        assert all(row.get("name") for row in rows), key
        assert all(row.get("admissions", 1) > 0 for row in rows), key


def test_condition_counts_sum_to_the_total():
    data = analytics.dashboard()
    total = sum(r["admissions"] for r in data["by_condition"])
    assert total == data["kpis"]["total_admissions"]


def test_months_are_in_chronological_order():
    months = [r["name"] for r in analytics.dashboard()["by_month"]]
    assert months == sorted(months)


def test_schema_describes_every_column():
    columns = analytics.schema_info()
    names = [c["name"] for c in columns]
    assert "admission_id" in names and "billing_amount" in names
    assert len(columns) == 23
    assert all(c["type"] in {"TEXT", "INTEGER", "REAL"} for c in columns)


def test_preprocessing_report_is_readable():
    report = analytics.preprocessing_report()
    assert report["rows_in"] >= report["rows_out"] > 0
    assert report["steps"]
