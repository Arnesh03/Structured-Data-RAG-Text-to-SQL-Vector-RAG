"""
Structured Data RAG — Unified Chat Interface

A Gradio-powered chat application that routes user queries to either:
  🗄️ Text-to-SQL pipeline (quantitative business questions)
  📄 Vector RAG pipeline (policy/FAQ document questions)

Run:  python app.py
"""
import gradio as gr

from router import route_query
from sql_chain import query_sql
from rag_chain import query_rag
from database import setup_database
from vectorstore import build_vectorstore, load_vectorstore
from config import DB_PATH, VECTORSTORE_DIR


# ── Initialization ────────────────────────────────────────────────────

def initialize():
    """Set up database and vector store if they don't exist."""
    if not DB_PATH.exists():
        print("🔧 Setting up database...")
        setup_database()
    else:
        print("✅ Database already exists.")

    if not VECTORSTORE_DIR.exists():
        print("🔧 Building vector store...")
        build_vectorstore()
    else:
        print("✅ Vector store already exists.")

    print("\n🚀 System ready!\n")


# ── Chat Handler ──────────────────────────────────────────────────────

def chat(message: str, history: list) -> str:
    """
    Process a user message: route it, run the appropriate pipeline,
    and return a formatted response.
    """
    if not message.strip():
        return "Please enter a question!"

    try:
        # Step 1: Route the query
        route = route_query(message)

        # Step 2: Run the appropriate pipeline
        if route == "sql":
            result = query_sql(message)
            # Format response with SQL transparency
            sql_query = result.get("sql_query", "N/A")
            response = (
                f"🗄️ **Routed to: SQL Database**\n\n"
                f"{result['answer']}\n\n"
                f"---\n"
                f"*Generated SQL:*\n```sql\n{sql_query}\n```"
            )
        else:
            result = query_rag(message)
            sources = result.get("sources", [])
            sources_str = ", ".join(sources) if sources else "N/A"
            response = (
                f"📄 **Routed to: Document RAG**\n\n"
                f"{result['answer']}\n\n"
                f"---\n"
                f"*Sources: {sources_str}*"
            )

        return response

    except Exception as e:
        return f"❌ **Error:** {str(e)}\n\nPlease check your OpenAI API key and try again."


# ── Gradio UI ─────────────────────────────────────────────────────────

DESCRIPTION = """
# 🔀 Structured Data RAG

**A hybrid RAG system with intelligent query routing.**

Ask me anything about:
- 🗄️ **Business data** — orders, revenue, products, customers (→ Text-to-SQL)
- 📄 **Policies & FAQ** — returns, shipping, payments, support (→ Vector RAG)

The system automatically detects your question type and routes it to the right pipeline.
"""

EXAMPLES = [
    "What is the average order value?",
    "What are the top 5 products by total revenue?",
    "How many orders were placed in each month?",
    "What is the return policy for electronics?",
    "How long does standard shipping take?",
    "What payment methods do you accept?",
    "How many orders were cancelled?",
    "Can I modify my order after placing it?",
    "What is the total revenue by category?",
    "How do I contact customer support?",
]


def build_app() -> gr.Blocks:
    """Build the Gradio app."""
    with gr.Blocks(
        title="Structured Data RAG",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
    ) as app:
        gr.Markdown(DESCRIPTION)

        chatbot = gr.ChatInterface(
            fn=chat,
            examples=EXAMPLES,
            cache_examples=False,
        )

    return app


# ── Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    initialize()
    app = build_app()
    app.launch(share=False)
