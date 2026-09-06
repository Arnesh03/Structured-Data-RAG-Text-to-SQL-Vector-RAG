"""
Shared LLM factory.

All three chains (router, SQL, RAG) use the same chat model. Building it is
cached so a chat turn doesn't pay client-construction cost three times over.

Three providers are supported. DeepSeek and OpenAI both speak the OpenAI API,
so they share a client and differ only in base URL; Groq has its own. Switch
with LLM_PROVIDER - nothing else in the project needs to change.
"""
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_MAX_RETRIES,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


class MissingAPIKeyError(RuntimeError):
    """Raised when the configured provider has no API key."""


@dataclass(frozen=True)
class Provider:
    """Everything that differs between one chat provider and the next."""

    name: str
    api_key: str
    model: str
    env_var: str
    console_url: str
    # None means the provider's own SDK; a URL means an OpenAI-compatible host.
    base_url: str | None = None


PROVIDERS = {
    "deepseek": Provider(
        name="deepseek",
        api_key=DEEPSEEK_API_KEY,
        model=DEEPSEEK_MODEL,
        env_var="DEEPSEEK_API_KEY",
        console_url="https://platform.deepseek.com/api_keys",
        base_url="https://api.deepseek.com/v1",
    ),
    "groq": Provider(
        name="groq",
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        env_var="GROQ_API_KEY",
        console_url="https://console.groq.com/keys",
    ),
    "openai": Provider(
        name="openai",
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        env_var="OPENAI_API_KEY",
        console_url="https://platform.openai.com/api-keys",
    ),
}

DEFAULT_PROVIDER = "groq"


def current() -> Provider:
    """The configured provider, falling back to the default for unknown names."""
    return PROVIDERS.get(LLM_PROVIDER, PROVIDERS[DEFAULT_PROVIDER])


def provider() -> str:
    """The configured provider's name."""
    return current().name


def model_name() -> str:
    """The chat model that will be used."""
    return current().model


def has_api_key() -> bool:
    """True when the configured provider has an API key."""
    return bool(current().api_key)


def require_api_key() -> None:
    """Raise a helpful error if the configured provider has no key."""
    if has_api_key():
        return
    p = current()
    raise MissingAPIKeyError(
        f"{p.env_var} is not set.\n\n"
        f"1. Get a key at {p.console_url}\n"
        f"2. Save it to a .env file in the project root:\n"
        f"     echo '{p.env_var}=your_key_here' >> .env\n"
        f"   (or export {p.env_var}=... in your shell)"
    )


@lru_cache(maxsize=None)
def get_llm(temperature: float = LLM_TEMPERATURE) -> BaseChatModel:
    """Return a cached chat model for the configured provider."""
    require_api_key()
    p = current()

    if p.name == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=p.model,
            temperature=temperature,
            max_retries=LLM_MAX_RETRIES,
            api_key=p.api_key,
        )

    # DeepSeek and OpenAI both speak the OpenAI API; only the host differs.
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=p.model,
        temperature=temperature,
        max_retries=LLM_MAX_RETRIES,
        api_key=p.api_key,
        base_url=p.base_url,
    )
