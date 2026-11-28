"""
Router evaluation. Deterministic.

Three numbers, kept apart on purpose:

  route_correct      did the pipeline send the question to the right arm
  fallback_used      did the LLM router fail and the keyword heuristic answer
  keyword_correct    would the heuristic alone have got it right

The third is free to compute and is the interesting one. If the heuristic
lands within a few points of the LLM, an LLM call can come out of the hot path
of every single query. If it trails badly, you have quantified what that
failure path costs. Either way it is a number a tutorial project cannot report.
"""
from __future__ import annotations


class RouterEvaluator:
    name = "router"
    deterministic = True

    def score(self, trace: dict, record) -> tuple[dict[str, float], dict]:
        predicted = trace.get("route_predicted")
        heuristic = trace.get("keyword_route")

        # An unanswerable question has no single correct arm, so routing is not
        # scored for it. Abstention is scored instead, by the generation evaluator.
        if not record.answerable:
            return {}, {"skipped": "unanswerable"}

        metrics: dict[str, float] = {
            "route_correct": float(predicted == record.route_label),
            "fallback_used": float(bool(trace.get("fallback_used"))),
        }
        if heuristic is not None:
            metrics["keyword_correct"] = float(heuristic == record.route_label)

        detail = {
            "expected": record.route_label,
            "predicted": predicted,
            "keyword_route": heuristic,
        }
        return metrics, detail


def confusion_matrix(traces: list[dict], dataset) -> dict[str, dict[str, int]]:
    """
    Counts of expected route against predicted route.

    Reported as a table, because the direction of the error is the finding:
    'we misroute aggregates into the policy arm' is actionable, '93% accurate'
    is not.
    """
    expected_of = {r.id: r.route_label for r in dataset if r.answerable}
    routes = ["sql", "rag", None]
    matrix = {e: {str(p): 0 for p in routes} for e in ("sql", "rag")}

    for trace in traces:
        expected = expected_of.get(trace["question_id"])
        if expected is None:
            continue
        matrix[expected][str(trace.get("route_predicted"))] += 1

    return matrix
