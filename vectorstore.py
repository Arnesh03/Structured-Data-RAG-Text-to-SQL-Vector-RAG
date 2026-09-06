"""
Policy PDF generator and FAISS vector store builder.

Renders the hospital policy corpus to PDF, then chunks and embeds it into a
FAISS index. The embedding model and the loaded index are cached, so a chat
turn does not re-load a sentence-transformer from disk.

The documents are written to PDF rather than embedded straight from Python
strings on purpose: the retrieval path exercises real PDF parsing, which is
what it would do against a hospital's actual policy library.

Run standalone:  python vectorstore.py [--force]
"""
import argparse
import shutil
from functools import lru_cache

from fpdf import FPDF
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    POLICIES_DIR,
    VECTORSTORE_DIR,
)
from policies_content import (
    ADMISSION_POLICY,
    CLINICAL_GUIDELINES,
    DISCHARGE_POLICY,
    INSURANCE_BILLING_POLICY,
    PATIENT_FAQ,
)

# filename -> (display title, sections)
DOCUMENTS = {
    "admission_policy.pdf": ("Patient Admission & Triage Policy", ADMISSION_POLICY),
    "insurance_billing_policy.pdf": ("Insurance, Billing & Financial Assistance Policy",
                                     INSURANCE_BILLING_POLICY),
    "clinical_guidelines.pdf": ("Clinical Care Guidelines", CLINICAL_GUIDELINES),
    "discharge_policy.pdf": ("Discharge, Follow-Up & Readmission Policy", DISCHARGE_POLICY),
    "patient_faq.pdf": ("Patient Rights & Frequently Asked Questions", PATIENT_FAQ),
}

# Friendly display names, used when citing sources back to the user.
SOURCE_TITLES = {name: title for name, (title, _) in DOCUMENTS.items()}


# ═══════════════════════════════════════════════════════════════════════
# PDF Generation
# ═══════════════════════════════════════════════════════════════════════

def _make_pdf(filename: str, title: str, sections: list[tuple[str, str]]) -> None:
    """Create a simple PDF with a title and multiple sections."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 17)
    pdf.multi_cell(0, 10, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "Metro General Hospital - Policy Manual", align="C",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    path = POLICIES_DIR / filename
    pdf.output(str(path))
    print(f"  Generated {path.name}")


def generate_policy_pdfs() -> None:
    """Generate every policy PDF in the corpus."""
    print("Generating policy PDFs...")
    for filename, (title, sections) in DOCUMENTS.items():
        _make_pdf(filename, title, sections)


# ═══════════════════════════════════════════════════════════════════════
# Vector Store
# ═══════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the cached local embedding model (downloaded once, then reused)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def load_policy_documents() -> list:
    """Load every policy PDF, tagging each page with its source file and title."""
    if not all((POLICIES_DIR / name).exists() for name in DOCUMENTS):
        generate_policy_pdfs()

    print("Loading PDFs...")
    all_docs = []
    for filename, (title, _) in DOCUMENTS.items():
        path = POLICIES_DIR / filename
        docs = PyPDFLoader(str(path)).load()
        for doc in docs:
            doc.metadata["source"] = filename
            doc.metadata["title"] = title
        all_docs.extend(docs)
        print(f"  Loaded {filename} ({len(docs)} page(s))")
    return all_docs


def build_vectorstore(force: bool = False) -> FAISS:
    """Load PDFs, chunk, embed, and build the FAISS vector store."""
    if force and VECTORSTORE_DIR.exists():
        shutil.rmtree(VECTORSTORE_DIR)

    all_docs = load_policy_documents()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)
    print(f"  Split into {len(chunks)} chunks")

    print("Building FAISS index...")
    vectorstore = FAISS.from_documents(chunks, get_embeddings())
    vectorstore.save_local(str(VECTORSTORE_DIR))
    print(f"  FAISS index saved to {VECTORSTORE_DIR}")

    load_vectorstore.cache_clear()
    return vectorstore


def vectorstore_is_ready() -> bool:
    """True when a saved FAISS index is present on disk."""
    return (VECTORSTORE_DIR / "index.faiss").exists() and (
        VECTORSTORE_DIR / "index.pkl"
    ).exists()


@lru_cache(maxsize=1)
def load_vectorstore() -> FAISS:
    """Load the FAISS vector store from disk (building it first if missing)."""
    if not vectorstore_is_ready():
        return build_vectorstore()
    return FAISS.load_local(
        str(VECTORSTORE_DIR),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )


def setup_vectorstore(force: bool = False) -> None:
    """Generate PDFs and build the index if it isn't already there."""
    if vectorstore_is_ready() and not force:
        print("  Vector store already exists - skipping (use force=True to rebuild).")
        return
    generate_policy_pdfs()
    build_vectorstore(force=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the FAISS policy index.")
    parser.add_argument("--force", action="store_true", help="rebuild even if it exists")
    setup_vectorstore(force=parser.parse_args().force)
