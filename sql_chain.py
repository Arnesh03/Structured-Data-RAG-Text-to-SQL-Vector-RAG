"""
Text-to-SQL pipeline using LangChain.

Connects to the SQLite e-commerce database and converts natural language
questions into SQL queries, executes them, and returns natural language answers.
"""
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_classic.chains.sql_database.query import create_sql_query_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from config import DB_PATH, GROQ_MODEL


# ── Custom Prompts ────────────────────────────────────────────────────

ANSWER_PROMPT = ChatPromptTemplate.from_template("""
Given the following user question, SQL query, and SQL result, provide a clear
and helpful natural language answer. Format numbers nicely (e.g., currency with
$ signs, percentages with % signs). If the result is a table, format it neatly.

Question: {question}
SQL Query: {query}
SQL Result: {result}

Answer:""")


def get_sql_chain():
    """Build and return the Text-to-SQL chain."""
    # Connect to SQLite
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

    # LLM
    llm = ChatGroq(model=GROQ_MODEL, temperature=0)

    # Chain that generates SQL from natural language
    sql_query_chain = create_sql_query_chain(llm, db)

    def run_query(query_text: str) -> str:
        """Execute SQL and return result."""
        # Clean up the query — remove markdown fences if present
        cleaned = query_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return db.run(cleaned)

    # Full chain: question → SQL → execute → natural language answer
    chain = (
        RunnablePassthrough.assign(
            query=sql_query_chain
        )
        .assign(
            result=lambda x: run_query(x["query"])
        )
        | ANSWER_PROMPT
        | llm
        | StrOutputParser()
    )

    return chain, sql_query_chain


def query_sql(question: str) -> dict:
    """
    Run a natural language question through the Text-to-SQL pipeline.

    Returns:
        dict with keys: 'answer', 'sql_query', 'route'
    """
    chain, sql_query_chain = get_sql_chain()

    # Get the generated SQL for transparency
    sql_query = sql_query_chain.invoke({"question": question})

    # Get the full answer
    answer = chain.invoke({"question": question})

    return {
        "answer": answer,
        "sql_query": sql_query.strip(),
        "route": "sql",
    }
