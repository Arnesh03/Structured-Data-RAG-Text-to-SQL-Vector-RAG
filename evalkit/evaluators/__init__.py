"""
Scoring. Every evaluator takes (trace, golden record) and returns metrics.

Three of the four are pure Python with no LLM in the loop, which means most of
the numbers this harness produces have no model variance in them at all. Say
that in the README: it is the difference between a measurement and an opinion.
"""
from evalkit.evaluators.generation import GenerationEvaluator
from evalkit.evaluators.retrieval import RetrievalEvaluator
from evalkit.evaluators.router import RouterEvaluator
from evalkit.evaluators.sql import SQLEvaluator

__all__ = ["RouterEvaluator", "SQLEvaluator", "RetrievalEvaluator", "GenerationEvaluator"]
