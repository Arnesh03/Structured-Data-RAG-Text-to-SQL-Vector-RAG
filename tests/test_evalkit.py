"""
Offline tests for the eval harness.

Everything here runs without an API key, a database or a network call. The
harness grades the pipeline; these grade the harness, and a metric nobody
tested is a number nobody should trust.
"""
import json
from types import SimpleNamespace

import pytest

from evalkit.config import ConfigError, EvalConfig
from evalkit.dataset import GoldenRecord, GoldenSet
from evalkit.evaluators.generation import looks_like_refusal
from evalkit.evaluators.retrieval import RetrievalEvaluator
from evalkit.evaluators.router import RouterEvaluator, confusion_matrix
from evalkit.evaluators.sql import normalize_cell, normalize_rows
from evalkit.judge_validate import cohens_kappa
from evalkit.store import TraceStore


# ── Config ────────────────────────────────────────────────────────────

def test_config_hash_ignores_key_order_and_value_type():
    a = EvalConfig.from_dict({"name": "a", "CHUNK_SIZE": 600, "RETRIEVER_TOP_K": 4})
    b = EvalConfig.from_dict({"name": "b", "RETRIEVER_TOP_K": "4", "CHUNK_SIZE": "600"})
    assert a.config_hash == b.config_hash


def test_config_hash_ignores_name_and_notes():
    a = EvalConfig.from_dict({"name": "x", "notes": "one", "CHUNK_SIZE": 600})
    b = EvalConfig.from_dict({"name": "y", "notes": "two", "CHUNK_SIZE": 600})
    assert a.config_hash == b.config_hash


def test_config_rejects_unknown_setting():
    # A typo must fail loudly, not silently evaluate the baseline twice.
    with pytest.raises(ConfigError, match="CHUNKSIZE"):
        EvalConfig.from_dict({"name": "typo", "CHUNKSIZE": 600})


def test_index_hash_only_tracks_index_settings():
    base = {"name": "a", "CHUNK_SIZE": 600, "RETRIEVER_TOP_K": 4}
    changed_k = dict(base, RETRIEVER_TOP_K=8)
    changed_chunk = dict(base, CHUNK_SIZE=300)

    a = EvalConfig.from_dict(base)
    assert a.index_hash == EvalConfig.from_dict(changed_k).index_hash  # shares an index
    assert a.index_hash != EvalConfig.from_dict(changed_chunk).index_hash


# ── Dataset ───────────────────────────────────────────────────────────

def _sql_record(**overrides):
    data = {
        "id": "q1", "question": "how many?", "route_label": "sql",
        "category": "aggregate_simple", "gold_sql": "SELECT COUNT(*) FROM admissions",
    }
    data.update(overrides)
    return data


def test_answerable_sql_question_requires_gold_sql():
    with pytest.raises(ValueError, match="needs gold_sql"):
        GoldenRecord(**_sql_record(gold_sql=None))


def test_answerable_rag_question_requires_gold_doc_ids():
    with pytest.raises(ValueError, match="needs gold_doc_ids"):
        GoldenRecord(id="q1", question="what are visiting hours?",
                     route_label="rag", category="faq")


def test_rag_question_rejects_unknown_source_document():
    with pytest.raises(ValueError, match="unknown source document"):
        GoldenRecord(id="q1", question="?", route_label="rag", category="faq",
                     gold_doc_ids=["not_a_real_policy.pdf"])


def test_unanswerable_question_needs_no_ground_truth():
    record = GoldenRecord(id="q1", question="what is the mortality rate?",
                          route_label="sql", category="unanswerable", answerable=False)
    assert record.gold_sql is None


def test_duplicate_ids_are_rejected():
    records = [GoldenRecord(**_sql_record()), GoldenRecord(**_sql_record())]
    with pytest.raises(ValueError, match="duplicate question ids"):
        GoldenSet(records)


def test_stratified_sample_spreads_across_categories():
    records = [
        GoldenRecord(**_sql_record(id=f"q{i}", category=f"cat{i % 4}"))
        for i in range(40)
    ]
    sample = GoldenSet(records).stratified_sample(8)
    assert len(sample) == 8
    # Not the first 8 rows, which would all be cat0..cat3 in order.
    assert len({r.category for r in sample}) == 4


def test_the_committed_golden_set_loads_and_validates():
    dataset = GoldenSet.load()
    summary = dataset.summary()
    assert summary["total"] > 0
    assert summary["unanswerable"] > 0, "a set with no unanswerable questions cannot measure hallucination"


# ── SQL execution accuracy ────────────────────────────────────────────

def test_integers_and_floats_compare_equal():
    assert normalize_cell(5) == normalize_cell(5.0)


def test_floats_are_rounded_before_comparison():
    assert normalize_cell(1.000000001) == normalize_cell(1.0)


def test_none_is_distinct_from_empty_string():
    assert normalize_cell(None) != normalize_cell("")


def test_column_order_is_ignored():
    assert normalize_rows([["a", 1]], ordered=False) == normalize_rows([[1, "a"]], ordered=False)


def test_row_order_ignored_unless_gold_has_order_by():
    gold = [["a"], ["b"]]
    shuffled = [["b"], ["a"]]
    assert normalize_rows(gold, ordered=False) == normalize_rows(shuffled, ordered=False)
    assert normalize_rows(gold, ordered=True) != normalize_rows(shuffled, ordered=True)


def test_duplicate_rows_are_significant():
    assert normalize_rows([["a"], ["a"]], ordered=False) != normalize_rows([["a"]], ordered=False)


# ── Router ────────────────────────────────────────────────────────────

def _record(**kw):
    defaults = {"id": "q1", "route_label": "sql", "answerable": True, "question": "?"}
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_router_scores_correct_route_and_keyword_separately():
    metrics, _ = RouterEvaluator().score(
        {"route_predicted": "sql", "keyword_route": "rag", "fallback_used": False},
        _record(route_label="sql"),
    )
    assert metrics["route_correct"] == 1.0
    assert metrics["keyword_correct"] == 0.0
    assert metrics["fallback_used"] == 0.0


def test_router_skips_unanswerable_questions():
    metrics, detail = RouterEvaluator().score(
        {"route_predicted": "sql"}, _record(answerable=False)
    )
    assert metrics == {}
    assert detail["skipped"] == "unanswerable"


def test_confusion_matrix_counts_direction_of_error():
    dataset = [_record(id="a", route_label="sql"), _record(id="b", route_label="rag")]
    traces = [
        {"question_id": "a", "route_predicted": "rag"},   # sql misrouted to rag
        {"question_id": "b", "route_predicted": "rag"},
    ]
    matrix = confusion_matrix(traces, dataset)
    assert matrix["sql"]["rag"] == 1
    assert matrix["sql"]["sql"] == 0
    assert matrix["rag"]["rag"] == 1


# ── Retrieval ─────────────────────────────────────────────────────────

def _rag_record(gold):
    return SimpleNamespace(id="q1", question="?", route_label="rag",
                           answerable=True, gold_doc_ids=gold)


def test_perfect_retrieval_scores_one_everywhere():
    trace = {"route_predicted": "rag",
             "chunks": [{"file": "patient_faq.pdf"}, {"file": "patient_faq.pdf"}]}
    metrics, _ = RetrievalEvaluator().score(trace, _rag_record(["patient_faq.pdf"]))
    assert metrics["precision_at_k"] == 1.0
    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg_at_k"] == 1.0


def test_mrr_reflects_the_rank_of_the_first_hit():
    trace = {"route_predicted": "rag", "chunks": [
        {"file": "admission_policy.pdf"}, {"file": "patient_faq.pdf"}]}
    metrics, detail = RetrievalEvaluator().score(trace, _rag_record(["patient_faq.pdf"]))
    assert metrics["mrr"] == 0.5
    assert metrics["precision_at_k"] == 0.5
    assert detail["first_hit_rank"] == 2


def test_retrieval_not_scored_when_misrouted():
    trace = {"route_predicted": "sql", "chunks": []}
    metrics, detail = RetrievalEvaluator().score(trace, _rag_record(["patient_faq.pdf"]))
    assert metrics == {"retrieval_attempted": 0.0}
    assert detail["reason"] == "misrouted"


# ── Abstention ────────────────────────────────────────────────────────

def test_refusal_is_recognised():
    assert looks_like_refusal(
        "I don't have information about that in the hospital policy documents.")


def test_a_real_answer_is_not_a_refusal():
    assert not looks_like_refusal("Visiting hours are 10am to 8pm daily.")
    assert not looks_like_refusal(None)


# ── Judge validation ──────────────────────────────────────────────────

def test_kappa_is_one_for_perfect_agreement():
    assert cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)


def test_kappa_is_zero_when_agreement_is_only_chance():
    # Both label half and half, agreeing on exactly half: no skill.
    assert cohens_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)


def test_kappa_punishes_a_constant_labeler():
    # The judge says "faithful" every time against a 50/50 truth. Percent
    # agreement would be 0.5; kappa correctly reports no skill.
    assert cohens_kappa([1, 1, 0, 0], [1, 1, 1, 1]) != pytest.approx(0.5)


# ── Store ─────────────────────────────────────────────────────────────

def test_traces_and_scores_round_trip(tmp_path):
    store = TraceStore(tmp_path / "t.db")
    config = EvalConfig.from_dict({"name": "baseline", "CHUNK_SIZE": 600})
    run_id = store.start_run(config, "golden.jsonl", 1)

    store.record(run_id, "q1", {
        "route": "sql", "keyword_route": "sql", "answer": "42",
        "sql_query": "SELECT 42", "rows": [[42]], "ok": True, "elapsed": 1.0,
    })
    store.write_scores(run_id, "q1", {"route_correct": 1.0, "sql_execution_accuracy": 0.0})
    store.finish_run(run_id)

    trace = store.traces(run_id)[0]
    assert trace["route_predicted"] == "sql"
    assert trace["rows"] == [[42]]
    assert store.aggregate(run_id) == {"route_correct": 1.0, "sql_execution_accuracy": 0.0}
    assert store.latest_run("baseline") == run_id


def test_rescoring_replaces_rather_than_duplicates(tmp_path):
    # The whole design rests on being able to re-score a run in place.
    store = TraceStore(tmp_path / "t.db")
    config = EvalConfig.from_dict({"name": "baseline"})
    run_id = store.start_run(config, "golden.jsonl", 1)

    store.write_scores(run_id, "q1", {"faithfulness": 0.0})
    store.write_scores(run_id, "q1", {"faithfulness": 1.0})
    assert store.aggregate(run_id) == {"faithfulness": 1.0}
