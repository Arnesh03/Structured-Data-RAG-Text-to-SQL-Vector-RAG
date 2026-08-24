# 🔀 Structured Data RAG: Text-to-SQL + Vector RAG

A hybrid Retrieval-Augmented Generation system with an intelligent query router that handles both **quantitative business queries** (via Text-to-SQL) and **qualitative policy questions** (via Vector RAG) in a single chat interface.

## ✨ Features

- **Intelligent Query Router** — LLM-based classifier that automatically routes questions to the right pipeline
- **Text-to-SQL Pipeline** — Converts natural language to SQL, executes on SQLite, returns human-readable answers
- **Vector RAG Pipeline** — Retrieves relevant policy documents from FAISS and generates grounded answers
- **Unified Gradio Chat UI** — Single interface with route indicators and SQL transparency
- **Self-Contained** — Generates its own fake data (1,000 e-commerce orders + 3 policy PDFs)

## 🏗️ Architecture

```
User Query
    │
    ▼
┌──────────┐
│  Router   │  (LLM classifies: "sql" or "rag")
└────┬─────┘
     │
     ├── sql ──► Text-to-SQL Chain ──► SQLite DB (1,000 orders)
     │                                      │
     │                                      ▼
     │                              Natural Language Answer
     │                              + Generated SQL Query
     │
     └── rag ──► Vector RAG Chain ──► FAISS (Policy PDFs)
                                           │
                                           ▼
                                   Natural Language Answer
                                   + Source Documents
```

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

### 3. Run the app

```bash
python app.py
```

The app will:
1. Generate 1,000 fake e-commerce orders → SQLite database
2. Generate 3 policy PDFs → FAISS vector store
3. Launch Gradio chat UI at `http://localhost:7860`

## 💬 Example Queries

| Query | Route | Pipeline |
|-------|-------|----------|
| "What is the average order value?" | 🗄️ SQL | Text-to-SQL |
| "Top 5 products by revenue" | 🗄️ SQL | Text-to-SQL |
| "How many orders in January?" | 🗄️ SQL | Text-to-SQL |
| "What is the return policy?" | 📄 RAG | Vector RAG |
| "How long does shipping take?" | 📄 RAG | Vector RAG |
| "What payment methods are accepted?" | 📄 RAG | Vector RAG |

## 🛠️ Tech Stack

- **LangChain** — Orchestration framework
- **OpenAI GPT-4o-mini** — LLM for routing, SQL generation, and answer synthesis
- **SQLite** — Structured data storage
- **FAISS** — Vector similarity search
- **Gradio** — Chat interface
- **Faker** — Synthetic data generation

## 📁 Project Structure

```
structured-data-rag/
├── app.py              # Gradio chat interface (entry point)
├── router.py           # LLM query router (sql/rag classification)
├── sql_chain.py        # Text-to-SQL pipeline
├── rag_chain.py        # Vector RAG pipeline
├── database.py         # SQLite + fake data generator
├── vectorstore.py      # PDF generator + FAISS builder
├── config.py           # Centralized configuration
├── requirements.txt    # Dependencies
├── README.md           # This file
└── data/
    ├── sales_data.csv
    ├── ecommerce.db
    ├── faiss_index/
    └── policies/
        ├── return_policy.pdf
        ├── shipping_policy.pdf
        └── faq.pdf
```
