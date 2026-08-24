"""
Centralized configuration for the Structured Data RAG project.
"""
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_DIR = DATA_DIR / "policies"
DB_PATH = DATA_DIR / "ecommerce.db"
CSV_PATH = DATA_DIR / "sales_data.csv"
VECTORSTORE_DIR = DATA_DIR / "faiss_index"

# ── LLM Settings ──────────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# ── Vector Store Settings ─────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RETRIEVER_TOP_K = 3

# ── Data Generation ──────────────────────────────────────────────────
NUM_ORDERS = 1000

# ── Ensure directories exist ─────────────────────────────────────────
DATA_DIR.mkdir(exist_ok=True)
POLICIES_DIR.mkdir(parents=True, exist_ok=True)
