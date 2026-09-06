"""
FastAPI backend for the Next.js frontend.

Everything the UI needs, in one process: the routed question-answering
pipeline (streamed as server-sent events so the browser can show each stage),
the dashboard aggregations, the database schema, and the preprocessing audit
trail.

Run:  python server.py      (or: uvicorn server:app --reload)
"""
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import analytics
from config import API_HOST, API_PORT, CORS_ORIGINS
from database import TABLE_NAME, database_is_ready
from llm import has_api_key, model_name, provider
from pipeline import EXAMPLE_QUESTIONS, answer, answer_events, initialize
from vectorstore import DOCUMENTS, vectorstore_is_ready


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Build the database and index, and warm the embedding model, on boot."""
    await asyncio.to_thread(initialize)
    yield


app = FastAPI(
    title="Healthcare Structured Data RAG",
    description="Router + Text-to-SQL + Vector RAG over hospital admissions data.",
    version="1.0.0",
    lifespan=lifespan,
)

# The Next.js dev server picks whatever port is free, so any localhost origin
# is allowed alongside the explicitly configured ones. Credentials stay off, so
# a permissive dev origin can't be used to read an authenticated response.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Metadata ──────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    """Readiness of every moving part, so the UI can explain what's missing."""
    return {
        "ok": True,
        "llm_provider": provider(),
        "llm_model": model_name(),
        "has_api_key": has_api_key(),
        "database_ready": database_is_ready(),
        "vectorstore_ready": vectorstore_is_ready(),
    }


@app.get("/api/examples")
def examples() -> list[dict]:
    """Seed questions for the chat UI, tagged with the route they should take."""
    return EXAMPLE_QUESTIONS


@app.get("/api/dashboard")
def dashboard() -> dict:
    """Every aggregate the analytics dashboard renders."""
    return analytics.dashboard()


@app.get("/api/schema")
def schema() -> dict:
    """The admissions table schema, with the comment on each column."""
    return {"table": TABLE_NAME, "columns": analytics.schema_info()}


@app.get("/api/preprocessing")
def preprocessing() -> dict:
    """The audit trail of what the cleaning pipeline changed and dropped."""
    return analytics.preprocessing_report()


@app.get("/api/documents")
def documents() -> list[dict]:
    """The policy documents backing the Vector RAG route."""
    return [
        {"file": name, "title": title, "sections": [h for h, _ in sections]}
        for name, (title, sections) in DOCUMENTS.items()
    ]


# ── Question answering ────────────────────────────────────────────────

@app.post("/api/ask")
async def ask(payload: Question) -> dict:
    """Answer a question and return the whole result at once."""
    return await asyncio.to_thread(answer, payload.question)


@app.post("/api/ask/stream")
async def ask_stream(payload: Question) -> StreamingResponse:
    """
    Answer a question as a stream of server-sent events.

    The pipeline is synchronous and LLM-bound, so it runs in a worker thread
    and hands events back through a queue rather than blocking the event loop.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    sentinel = object()

    def produce() -> None:
        try:
            for event in answer_events(payload.question):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:  # noqa: BLE001 - never strand the client
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "message": str(exc)}
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    async def events():
        task = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while True:
                event = await queue.get()
                if event is sentinel:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await task

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host=API_HOST, port=API_PORT, reload=False)
