/**
 * How a metric value becomes a colour.
 *
 * Green, amber and red carry meaning here rather than decoration: every tinted
 * thing on the Evals tab is tinted because its value crossed a stated
 * threshold, and the thresholds live in one place so two panels can never
 * disagree about what "good" is.
 */
export type Tone = "good" | "warn" | "bad" | "neutral";

/** Metrics where a smaller number is the better outcome. */
export const LOWER_IS_BETTER = new Set([
  "hallucinated",
  "sql_invalid",
  "fallback_used",
]);

/**
 * [good at or above, warn at or above] for higher-is-better metrics, and
 * [good at or below, warn at or below] for the lower-is-better ones.
 *
 * Retrieval sits lower than routing on purpose: precision@k is bounded by how
 * many of the k chunks can possibly be relevant, so holding it to 0.85 would
 * paint a healthy retriever red.
 */
const THRESHOLDS: Record<string, [number, number]> = {
  route_correct: [0.9, 0.75],
  keyword_correct: [0.8, 0.6],
  sql_execution_accuracy: [0.8, 0.6],
  precision_at_k: [0.6, 0.4],
  recall_at_k: [0.85, 0.65],
  mrr: [0.75, 0.5],
  ndcg_at_k: [0.75, 0.5],
  faithfulness: [0.9, 0.75],
  answer_relevance: [0.9, 0.75],
  answer_correctness: [0.85, 0.7],
  abstained: [0.9, 0.7],

  // Lower is better.
  hallucinated: [0.05, 0.15],
  sql_invalid: [0.02, 0.08],
  fallback_used: [0.05, 0.2],
};

const DEFAULT_HIGHER: [number, number] = [0.85, 0.65];
const DEFAULT_LOWER: [number, number] = [0.05, 0.15];

export function toneOf(metric: string, value: number | undefined): Tone {
  if (value === undefined || Number.isNaN(value)) return "neutral";

  const lower = LOWER_IS_BETTER.has(metric);
  const [good, warn] =
    THRESHOLDS[metric] ?? (lower ? DEFAULT_LOWER : DEFAULT_HIGHER);

  if (lower) {
    if (value <= good) return "good";
    return value <= warn ? "warn" : "bad";
  }
  if (value >= good) return "good";
  return value >= warn ? "warn" : "bad";
}

/** Tailwind classes per tone, from the theme tokens rather than raw hex. */
export const TONE_TEXT: Record<Tone, string> = {
  good: "text-positive",
  warn: "text-warn",
  bad: "text-danger",
  neutral: "text-faint",
};

export const TONE_BG: Record<Tone, string> = {
  good: "bg-positive-soft",
  warn: "bg-warn-soft",
  bad: "bg-danger-soft",
  neutral: "bg-surface-2",
};

/** For bars and rings, where a token has to be a raw colour value. */
export const TONE_VAR: Record<Tone, string> = {
  good: "var(--positive)",
  warn: "var(--warn)",
  bad: "var(--danger)",
  neutral: "var(--text-3)",
};

export const METRIC_LABELS: Record<string, string> = {
  route_correct: "Routing accuracy",
  keyword_correct: "Keyword heuristic",
  fallback_used: "Fallback rate",
  sql_execution_accuracy: "Execution accuracy",
  sql_invalid: "Invalid SQL",
  sql_exact_match: "Exact match",
  sql_attempted: "Attempted",
  retrieval_attempted: "Attempted",
  precision_at_k: "Precision@k",
  recall_at_k: "Recall@k",
  mrr: "MRR",
  ndcg_at_k: "nDCG@k",
  faithfulness: "Faithfulness",
  answer_relevance: "Relevance",
  answer_correctness: "Correctness",
  answered: "Answered",
  abstained: "Abstention rate",
  hallucinated: "Hallucination rate",
};

export const METRIC_HINTS: Record<string, string> = {
  route_correct: "Share of questions sent to the right arm",
  keyword_correct: "What the keyword heuristic alone would have scored",
  fallback_used: "How often the LLM router failed and the heuristic answered",
  sql_execution_accuracy: "Generated SQL returned the same rows as the gold query",
  sql_invalid: "Generated SQL that raised on execution",
  precision_at_k: "Retrieved chunks that came from a gold document",
  recall_at_k: "Gold documents found anywhere in the top k",
  mrr: "1 / rank of the first relevant chunk",
  ndcg_at_k: "Rank-aware retrieval quality",
  faithfulness: "Claims in the answer supported by the retrieved context",
  answer_relevance: "Answers that address the question asked",
  answer_correctness: "Answers that agree with the reference",
  abstained: "Unanswerable questions the system declined",
  hallucinated: "Unanswerable questions it answered anyway",
};

export const METRIC_GROUPS: {
  id: string;
  title: string;
  blurb: string;
  metrics: string[];
}[] = [
  {
    id: "router",
    title: "Router",
    blurb: "Deterministic. Which arm each question reached, and how often the LLM router fell back to keywords.",
    metrics: ["route_correct", "keyword_correct", "fallback_used"],
  },
  {
    id: "sql",
    title: "Text-to-SQL",
    blurb: "Deterministic. Graded on whether the query returns the same rows as gold, never on string similarity.",
    metrics: ["sql_execution_accuracy", "sql_invalid", "sql_exact_match"],
  },
  {
    id: "retrieval",
    title: "Vector retrieval",
    blurb: "Deterministic. Precision counts chunks, recall counts documents, because ground truth is document-level.",
    metrics: ["precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"],
  },
  {
    id: "generation",
    title: "Generation",
    blurb: "Judged by an LLM. Worth nothing until the judge is validated against human labels — run make eval-kappa.",
    metrics: ["faithfulness", "answer_relevance", "answer_correctness"],
  },
  {
    id: "safety",
    title: "Abstention",
    blurb: "Deterministic. Measured only on the unanswerable questions, which are deliberate near-misses on real content.",
    metrics: ["abstained", "hallucinated"],
  },
];

export const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export const label = (metric: string) => METRIC_LABELS[metric] ?? metric;
