"""
Generation evaluation. The only evaluator with a model in the loop.

Two kinds of measurement live here:

  abstention   deterministic. On the unanswerable questions, did the system
               decline? This is the hallucination number, and it is the one
               worth leading a README with.
  judged       faithfulness, relevance and correctness, graded by an LLM.

The judged numbers are worth nothing until the judge is validated against
human labels. `evalkit.judge_validate` does that and reports Cohen's kappa.
Report the kappa next to these metrics, always.

Judge calls are cached on (judge prompt, question, answer), so re-scoring an
unchanged answer never pays twice.
"""
from __future__ import annotations

import json
import re

from evalkit.cache import JsonCache, digest

# Kept in sync with rag_chain.NO_ANSWER; imported lazily so this module can be
# unit-tested without pulling in LangChain.
_REFUSAL_PATTERNS = (
    "i don't have information about that",
    "i do not have information about that",
    "not in the hospital policy documents",
    "i don't know",
    "i cannot answer",
    "no information available",
)

JUDGE_PROMPT = """\
You are grading one answer from a hospital question-answering system.

Question:
{question}

Context the system was given:
{context}

Answer the system produced:
{answer}

Reference answer (may be empty if none was recorded):
{reference}

Grade three things, each 0 or 1:

faithful: 1 if every factual claim in the answer is supported by the context.
  0 if any claim is absent from, or contradicts, the context. If the answer
  declines to answer and the context genuinely lacks the information, that is
  faithful (1).
relevant: 1 if the answer addresses the question that was asked. An evasive or
  off-topic answer is 0.
correct: 1 if the answer agrees with the reference answer on the substance. If
  no reference is recorded, judge against the context instead.

Respond with ONLY a JSON object and nothing else:
{{"faithful": 0 or 1, "relevant": 0 or 1, "correct": 0 or 1, "why": "one short sentence"}}
"""


def looks_like_refusal(answer: str | None) -> bool:
    """Whether an answer declines rather than asserting something."""
    if not answer:
        return False
    lowered = answer.lower()
    return any(pattern in lowered for pattern in _REFUSAL_PATTERNS)


def _context_of(trace: dict) -> str:
    """Reconstruct what the generator actually saw, for faithfulness grading."""
    chunks = trace.get("chunks") or []
    if chunks:
        return "\n\n---\n\n".join(
            f"[{c.get('title', c.get('file'))}]\n{c.get('text', '')}" for c in chunks
        )
    rows = trace.get("rows")
    if rows is not None:
        return f"SQL query:\n{trace.get('sql_query')}\n\nRows returned:\n{json.dumps(rows)[:4000]}"
    return ""


def _parse_verdict(raw: str) -> dict | None:
    """Pull a JSON verdict out of a possibly chatty judge response."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not all(key in data for key in ("faithful", "relevant", "correct")):
        return None
    return data


class GenerationEvaluator:
    name = "generation"
    deterministic = False

    def __init__(self, use_judge: bool = True):
        self.use_judge = use_judge
        self.cache = JsonCache("judge")
        self.prompt_hash = digest(JUDGE_PROMPT)

    def _judge(self, question: str, context: str, answer: str, reference: str) -> dict | None:
        key = digest(self.prompt_hash, question, answer, reference)

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        try:
            from llm import get_llm
            raw = get_llm(temperature=0.0).invoke(
                JUDGE_PROMPT.format(
                    question=question,
                    context=context[:6000] or "(no context recorded)",
                    answer=answer,
                    reference=reference or "(none recorded)",
                )
            )
            text = getattr(raw, "content", str(raw))
        except Exception as exc:  # noqa: BLE001 - a judge outage is not a test failure
            return {"error": f"{type(exc).__name__}: {exc}"}

        verdict = _parse_verdict(text)
        if verdict is None:
            return {"error": "judge returned unparseable output", "raw": text[:400]}

        self.cache.set(key, verdict)
        return verdict

    def score(self, trace: dict, record) -> tuple[dict[str, float], dict]:
        answer = trace.get("answer") or ""

        # ── Unanswerable: the only correct behaviour is to decline ─────
        if not record.answerable:
            abstained = looks_like_refusal(answer)
            return (
                {"abstained": float(abstained), "hallucinated": float(not abstained)},
                {"answer": answer[:300]},
            )

        if not trace.get("ok"):
            return {"answered": 0.0}, {"error": trace.get("error")}

        metrics: dict[str, float] = {"answered": 1.0}
        detail: dict = {}

        if self.use_judge:
            verdict = self._judge(
                record.question, _context_of(trace), answer, record.gold_answer or ""
            )
            if verdict and "error" not in verdict:
                metrics.update({
                    "faithfulness": float(verdict["faithful"]),
                    "answer_relevance": float(verdict["relevant"]),
                    "answer_correctness": float(verdict["correct"]),
                })
                detail["why"] = verdict.get("why", "")
            elif verdict:
                detail["judge_error"] = verdict.get("error")

        return metrics, detail
