"""
Evaluation harness for the Structured Data RAG pipeline.

The harness imports the pipeline as a library and never reaches inside it, so
the two can change independently. Running and scoring are deliberately
separate: `runner` records raw traces, `evaluators` score them afterwards.
That means adding a metric re-scores every past run without re-running the
pipeline or paying for the LLM calls again.
"""
__all__ = ["config", "dataset", "store", "cache", "runner", "report"]
