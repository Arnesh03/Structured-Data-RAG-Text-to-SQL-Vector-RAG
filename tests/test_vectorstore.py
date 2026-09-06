"""Policy PDFs, the FAISS index, and retrieval relevance."""
import pytest

from config import POLICIES_DIR
from rag_chain import NO_ANSWER, format_docs, get_retriever, query_rag
from vectorstore import DOCUMENTS, SOURCE_TITLES, load_vectorstore, vectorstore_is_ready


def test_policy_pdfs_exist():
    for name in DOCUMENTS:
        assert (POLICIES_DIR / name).exists(), f"missing {name}"


def test_index_is_built():
    assert vectorstore_is_ready(), "run `python cli.py --setup` first"


def test_chunks_carry_source_metadata():
    docs = load_vectorstore().similarity_search("triage levels", k=3)
    assert docs
    for doc in docs:
        assert doc.metadata["source"] in SOURCE_TITLES
        assert doc.metadata["title"]


@pytest.mark.parametrize("question,expected_source", [
    ("What are the emergency department triage levels?", "admission_policy.pdf"),
    ("Who qualifies for charity care?", "insurance_billing_policy.pdf"),
    ("What is the inpatient blood glucose target?", "clinical_guidelines.pdf"),
    ("When is a follow-up appointment scheduled after discharge?",
     "discharge_policy.pdf"),
    ("How do I get a copy of my medical records?", "patient_faq.pdf"),
])
def test_retrieval_finds_the_right_document(question, expected_source):
    docs = get_retriever().invoke(question)
    assert expected_source in {d.metadata["source"] for d in docs}


def test_format_docs_labels_every_source():
    docs = get_retriever().invoke("medication reconciliation")
    context = format_docs(docs)
    assert context.count("[Source:") == len(docs)


def test_query_rag_returns_answer_sources_and_chunks(fake_llm):
    fake_llm("Level 1 patients are seen immediately.")
    result = query_rag("What are the triage levels?")
    assert result["route"] == "rag"
    assert "immediately" in result["answer"]
    assert {s["file"] for s in result["sources"]} <= set(SOURCE_TITLES)
    assert all(s["title"] for s in result["sources"])
    assert result["chunks"] and all(c["text"] for c in result["chunks"])


def test_sources_are_deduplicated(fake_llm):
    fake_llm("ok")
    files = [s["file"] for s in query_rag("discharge criteria")["sources"]]
    assert len(files) == len(set(files))


def test_ungrounded_question_can_return_the_refusal(fake_llm):
    fake_llm(NO_ANSWER)
    assert query_rag("Who won the 1998 World Cup?")["answer"] == NO_ANSWER
