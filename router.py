"""
Intelligent Query Router.

Uses an LLM to classify user queries as either:
  - "sql"  → quantitative questions about e-commerce data (orders, revenue, counts)
  - "rag"  → qualitative questions about policies, FAQ, shipping, returns

Falls back to RAG if uncertain.
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import OPENAI_MODEL

# ── Router Prompt ─────────────────────────────────────────────────────

ROUTER_PROMPT = ChatPromptTemplate.from_template("""
You are a query router for an e-commerce support system. Your job is to classify
the user's question into exactly one of two categories:

1. "sql" — The question is about quantitative data, metrics, or business analytics.
   Examples: order counts, revenue, average values, top products, sales trends,
   customer counts, order status distribution, specific order lookups.

2. "rag" — The question is about company policies, procedures, FAQs, or qualitative
   information. Examples: return policy, shipping details, payment methods,
   account creation, gift wrapping, customer support contact info.

Respond with ONLY the word "sql" or "rag". Nothing else.

User question: {question}

Classification:""")


def get_router():
    """Build and return the query router chain."""
    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
    chain = ROUTER_PROMPT | llm | StrOutputParser()
    return chain


def route_query(question: str) -> str:
    """
    Classify a user question as 'sql' or 'rag'.

    Args:
        question: The user's natural language question.

    Returns:
        'sql' or 'rag'
    """
    router = get_router()
    result = router.invoke({"question": question}).strip().lower()

    # Ensure valid output — default to rag if unclear
    if result not in ("sql", "rag"):
        print(f"  ⚠️  Router returned unexpected value: '{result}', defaulting to 'rag'")
        return "rag"

    return result
