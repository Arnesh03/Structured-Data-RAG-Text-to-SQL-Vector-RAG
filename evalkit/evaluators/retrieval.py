"""
Retrieval evaluation. Deterministic.

Ground truth is document-level: `gold_doc_ids` names the policy PDFs that
contain the answer. Retrieval is chunk-level, and several chunks can come from
one document, so precision counts chunks while recall counts documents. That
asymmetry is deliberate and worth stating in the README:

  precision@k   of the k chunks retrieved, how many came from a gold document
  recall@k      of the gold documents, how many appear anywhere in the top k
  MRR           1 / rank of the first chunk from a gold document
  nDCG@k        rank-aware, binary relevance

MRR and nDCG are what catch "the right document was retrieved, ranked fourth",
which plain precision hides and which a reranker is supposed to fix.
"""
from __future__ import annotations

import math


def _retrieved_files(trace: dict) -> list[str]:
    """Files behind the retrieved chunks, in retrieval order."""
    chunks = trace.get("chunks") or []
    files = [c.get("file") for c in chunks if c.get("file")]
    if files:
        return files
    # Older traces recorded only the de-duplicated source list.
    return [s.get("file") for s in (trace.get("sources") or []) if s.get("file")]


class RetrievalEvaluator:
    name = "retrieval"
    deterministic = True

    def score(self, trace: dict, record) -> tuple[dict[str, float], dict]:
        if record.route_label != "rag" or not record.answerable or not record.gold_doc_ids:
            return {}, {}

        if trace.get("route_predicted") != "rag":
            return {"retrieval_attempted": 0.0}, {"reason": "misrouted"}

        retrieved = _retrieved_files(trace)
        if not retrieved:
            return {
                "retrieval_attempted": 1.0,
                "precision_at_k": 0.0,
                "recall_at_k": 0.0,
                "mrr": 0.0,
                "ndcg_at_k": 0.0,
            }, {"reason": "nothing retrieved"}

        gold = set(record.gold_doc_ids)
        k = len(retrieved)
        relevance = [1 if f in gold else 0 for f in retrieved]

        precision = sum(relevance) / k
        recall = len(set(retrieved) & gold) / len(gold)

        first = next((i for i, hit in enumerate(relevance, start=1) if hit), None)
        mrr = 1.0 / first if first else 0.0

        # Ground truth is document-level but retrieval is chunk-level, so the
        # number of relevant CHUNKS in the corpus is not knowable here. The
        # ideal ranking is therefore the relevant chunks that were retrieved,
        # all placed at the top: nDCG then measures how well what was found
        # was ranked, and stays in [0, 1].
        dcg = sum(hit / math.log2(i + 1) for i, hit in enumerate(relevance, start=1))
        ideal_hits = min(sum(relevance), k)
        idcg = sum(1 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
        ndcg = dcg / idcg if idcg else 0.0

        metrics = {
            "retrieval_attempted": 1.0,
            "precision_at_k": precision,
            "recall_at_k": recall,
            "mrr": mrr,
            "ndcg_at_k": ndcg,
        }
        detail = {"k": k, "retrieved": retrieved, "gold": sorted(gold), "first_hit_rank": first}
        return metrics, detail
