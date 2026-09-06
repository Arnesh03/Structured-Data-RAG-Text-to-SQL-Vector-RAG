"""Shared fixtures. The whole suite runs offline - no LLM API key required."""
import sys
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm  # noqa: E402
import rag_chain  # noqa: E402
import router  # noqa: E402
import sql_chain  # noqa: E402

_CACHED = (
    router.get_router,
    sql_chain.get_sql_generator,
    sql_chain.get_answer_chain,
    rag_chain.get_answer_chain,
    rag_chain.get_retriever,
    llm.get_llm,
)


@pytest.fixture(autouse=True)
def clear_chain_caches():
    """Chains are lru_cached; drop them so patched LLMs actually take effect."""
    for fn in _CACHED:
        fn.cache_clear()
    yield
    for fn in _CACHED:
        fn.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch):
    """Install a scripted chat model in place of the real provider."""

    def install(*responses: str) -> FakeListChatModel:
        model = FakeListChatModel(responses=list(responses))
        for module in (router, sql_chain, rag_chain):
            monkeypatch.setattr(module, "get_llm", lambda *a, **k: model)
        return model

    return install
