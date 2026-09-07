"""
Centralized configuration for the Structured Data RAG project.

Every value can be overridden with an environment variable, which may be set
in the shell or in a `.env` file at the project root (see `.env.example`).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env (shell environment always wins) ─────────────────────────
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


# ── Paths ─────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_DIR = DATA_DIR / "policies"

RAW_CSV_PATH = Path(os.getenv("RAW_CSV_PATH", PROJECT_ROOT / "healthcare_dataset.csv"))
CLEAN_CSV_PATH = DATA_DIR / "healthcare_clean.csv"
REPORT_PATH = DATA_DIR / "preprocessing_report.json"
DB_PATH = DATA_DIR / "healthcare.db"
VECTORSTORE_DIR = DATA_DIR / "faiss_index"

# ── LLM settings ──────────────────────────────────────────────────────
# "deepseek", "groq" (free tier, very fast), or "openai".
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Groq retires models fairly often. If this one 404s, check what your key can
# reach at https://console.groq.com/docs/models and override with GROQ_MODEL.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LLM_TEMPERATURE = _float_env("LLM_TEMPERATURE", 0.0)
LLM_MAX_RETRIES = _int_env("LLM_MAX_RETRIES", 2)

# ── Embedding settings (local HuggingFace — free, no API key) ─────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# ── Vector store settings ────────────────────────────────────────────
CHUNK_SIZE = _int_env("CHUNK_SIZE", 600)
CHUNK_OVERLAP = _int_env("CHUNK_OVERLAP", 80)
RETRIEVER_TOP_K = _int_env("RETRIEVER_TOP_K", 4)

# ── SQL settings ─────────────────────────────────────────────────────
# Hard cap on rows returned to the LLM, so a broad query can't blow up the
# context window.
SQL_MAX_ROWS = _int_env("SQL_MAX_ROWS", 20)

# ── Preprocessing ────────────────────────────────────────────────────
# Length of stay above this many days is treated as a data-entry error.
MAX_STAY_DAYS = _int_env("MAX_STAY_DAYS", 365)

# ── Servers ──────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "127.0.0.1")
# Most hosts (Hugging Face Spaces, Render, Railway, Fly) inject PORT.
API_PORT = _int_env("PORT", _int_env("API_PORT", 8010))
# Origins allowed to call the FastAPI backend (the Next.js dev server).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_SERVER_PORT = _int_env("GRADIO_SERVER_PORT", 7860)

# ── Ensure directories exist ─────────────────────────────────────────
DATA_DIR.mkdir(exist_ok=True)
POLICIES_DIR.mkdir(parents=True, exist_ok=True)
