"""
Healthcare Structured Data RAG - Gradio chat interface.

A dependency-light fallback UI: the same routed pipeline as the Next.js
frontend, without needing Node installed. Run `make web` for the full
dashboard experience.

Run:  python app.py
"""
import gradio as gr

from config import GRADIO_SERVER_NAME, GRADIO_SERVER_PORT
from pipeline import EXAMPLE_QUESTIONS, answer, format_response, initialize

DESCRIPTION = """\
# 🏥 Healthcare Structured Data RAG

**A hybrid RAG system with intelligent query routing over 54,966 hospital admissions.**

Ask about:
- 🗄️ **Patient data** - conditions, billing, length of stay, admission types → *Text-to-SQL over SQLite*
- 📄 **Hospital policy** - triage, insurance rules, clinical protocols, patient rights → *Vector RAG over FAISS*

The router classifies each question and sends it down the right pipeline. Every answer
shows the route it took, plus the SQL that ran or the documents it cited.
"""


def chat(message: str, history: list) -> str:
    """Route the message, run the matching pipeline, return markdown."""
    return format_response(answer(message))


def build_app() -> gr.Blocks:
    """Build the Gradio app."""
    theme = gr.themes.Soft(primary_hue="teal", secondary_hue="slate")
    with gr.Blocks(title="Healthcare Structured Data RAG", theme=theme,
                   fill_height=True) as app:
        gr.Markdown(DESCRIPTION)
        gr.ChatInterface(
            fn=chat,
            chatbot=gr.Chatbot(
                height=440,
                show_label=False,
                placeholder="Ask a question, or pick one of the examples below.",
            ),
            examples=[ex["q"] for ex in EXAMPLE_QUESTIONS],
            cache_examples=False,
        )
    return app


if __name__ == "__main__":
    initialize()
    build_app().launch(
        server_name=GRADIO_SERVER_NAME,
        server_port=GRADIO_SERVER_PORT,
        share=False,
    )
