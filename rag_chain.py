"""
Vector RAG pipeline for hospital policy and clinical guideline retrieval.

Retrieves the most relevant policy chunks from FAISS and answers strictly from
them. Retrieval happens once per question and the same documents are used for
both the answer and the cited sources, so a citation always points at text the
model actually saw.
"""
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import RETRIEVER_TOP_K
from llm import get_llm
from vectorstore import SOURCE_TITLES, load_vectorstore

NO_ANSWER = "I don't have information about that in the hospital policy documents."

# ── RAG Prompt ────────────────────────────────────────────────────────

RAG_PROMPT = ChatPromptTemplate.from_template("""\
You are a hospital information assistant. Answer the question using ONLY the
context below, which is drawn from the hospital's official policy manual and
clinical guidelines.

Rules:
- If the context does not contain the answer, reply exactly:
  "{no_answer}"
- Do not use outside knowledge and do not guess.
- Be specific: quote concrete numbers, thresholds, timeframes, and fees when
  they appear in the context.
- Name the document each piece of information comes from.
- These are institutional policies and general clinical protocols. Do not give
  medical advice for an individual patient; if the question asks for personal
  medical guidance, state the relevant policy and say the care team decides
  the individual case.

Context:
{context}

Question: {question}

Answer:""")


def format_docs(docs) -> str:
    """Format retrieved documents into a single context string."""
    blocks = []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown")
        title = doc.metadata.get("title", SOURCE_TITLES.get(source, source))
        blocks.append(f"[Source: {title} ({source})]\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(blocks)


@lru_cache(maxsize=1)
def get_retriever(top_k: int = RETRIEVER_TOP_K):
    """Return the cached FAISS retriever."""
    return load_vectorstore().as_retriever(search_kwargs={"k": top_k})


@lru_cache(maxsize=1)
def get_answer_chain():
    """Chain: (context, question) -> grounded answer."""
    return RAG_PROMPT | get_llm() | StrOutputParser()


def query_rag(question: str) -> dict:
    """
    Run a question through the Vector RAG pipeline.

    Returns a dict with keys: 'answer', 'sources', 'chunks', 'route'.
    Each source carries the filename and its human-readable title; each chunk
    carries its text alongside the document it came from, so the UI can show
    the evidence next to the answer.
    """
    docs = get_retriever().invoke(question)

    if not docs:
        return {"answer": NO_ANSWER, "sources": [], "chunks": [], "route": "rag"}

    answer = get_answer_chain().invoke({
        "context": format_docs(docs),
        "question": question,
        "no_answer": NO_ANSWER,
    })

    # Preserve retrieval order while de-duplicating.
    sources: list[dict] = []
    seen: set[str] = set()
    chunks: list[dict] = []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown")
        title = doc.metadata.get("title", SOURCE_TITLES.get(source, source))
        if source not in seen:
            seen.add(source)
            sources.append({"file": source, "title": title})
        chunks.append({
            "file": source,
            "title": title,
            "page": doc.metadata.get("page"),
            "text": doc.page_content.strip(),
        })

    return {
        "answer": answer,
        "sources": sources,
        "chunks": chunks,
        "route": "rag",
    }
