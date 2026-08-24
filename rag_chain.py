"""
Vector RAG pipeline for policy/FAQ document retrieval.

Uses FAISS vector store to retrieve relevant document chunks and generates
answers grounded in the retrieved context.
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from config import OPENAI_MODEL, RETRIEVER_TOP_K
from vectorstore import load_vectorstore


# ── RAG Prompt ────────────────────────────────────────────────────────

RAG_PROMPT = ChatPromptTemplate.from_template("""
You are a helpful customer support assistant. Answer the question based ONLY on
the provided context from our policy documents. If the answer is not found in
the context, say "I don't have information about that in our policy documents."

Be specific and cite which document the information comes from when possible.

Context:
{context}

Question: {question}

Answer:""")


def format_docs(docs) -> str:
    """Format retrieved documents into a single context string."""
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown")
        formatted.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)


def get_rag_chain():
    """Build and return the Vector RAG chain."""
    # Load vector store
    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_TOP_K})

    # LLM
    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)

    # RAG chain
    chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | RAG_PROMPT
        | llm
        | StrOutputParser()
    )

    return chain, retriever


def query_rag(question: str) -> dict:
    """
    Run a question through the Vector RAG pipeline.

    Returns:
        dict with keys: 'answer', 'sources', 'route'
    """
    chain, retriever = get_rag_chain()

    # Get answer
    answer = chain.invoke(question)

    # Get source documents for transparency
    source_docs = retriever.invoke(question)
    sources = list({doc.metadata.get("source", "Unknown") for doc in source_docs})

    return {
        "answer": answer,
        "sources": sources,
        "route": "rag",
    }
