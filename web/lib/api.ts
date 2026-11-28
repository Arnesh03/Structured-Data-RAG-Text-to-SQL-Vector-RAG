import type {
  Dashboard,
  ExampleQuestion,
  Health,
  PolicyDocument,
  PreprocessingReport,
  CandidatePayload,
  CandidateQueued,
  EvalDataset,
  EvalRunDetail,
  EvalSummary,
  TryResult,
  SchemaColumn,
  StreamEvent,
} from "./types";

/**
 * The FastAPI backend.
 *
 * In a production build this defaults to the empty string, i.e. the same
 * origin the page was served from - which is how the single-container deploy
 * works, with FastAPI serving both the API and this bundle. In development the
 * two run on separate ports, so it points at the local backend. Either can be
 * overridden with NEXT_PUBLIC_API_URL.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "")
  ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8010" : "");

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/**
 * POST and parse, surfacing FastAPI's `detail` rather than a bare status.
 *
 * The eval endpoints reject bad input with a real validation message — "an
 * answerable sql question needs gold_sql" — and that message is the whole
 * value of the response, so it must reach the user rather than "422".
 */
async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const payload = await res.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      /* a non-JSON error body; the status line is all we have */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const getHealth = (s?: AbortSignal) => getJson<Health>("/api/health", s);
export const getDashboard = (s?: AbortSignal) => getJson<Dashboard>("/api/dashboard", s);
export const getExamples = (s?: AbortSignal) =>
  getJson<ExampleQuestion[]>("/api/examples", s);
export const getDocuments = (s?: AbortSignal) =>
  getJson<PolicyDocument[]>("/api/documents", s);
export const getPreprocessing = (s?: AbortSignal) =>
  getJson<PreprocessingReport>("/api/preprocessing", s);
export const getSchema = (s?: AbortSignal) =>
  getJson<{ table: string; columns: SchemaColumn[] }>("/api/schema", s);

/* The eval harness is read-only over the trace store; see evalkit/api.py. */
export const getEvalSummary = (s?: AbortSignal) =>
  getJson<EvalSummary>("/api/eval/summary", s);
export const getEvalDataset = (s?: AbortSignal) =>
  getJson<EvalDataset>("/api/eval/dataset", s);
export const getEvalRun = (runId: string, s?: AbortSignal) =>
  getJson<EvalRunDetail>(`/api/eval/runs/${encodeURIComponent(runId)}`, s);

/** Runs one ad-hoc question through the live pipeline. Nothing is stored. */
export const tryQuestion = (
  question: string,
  expectUnanswerable: boolean,
  s?: AbortSignal,
) =>
  postJson<TryResult>(
    "/api/eval/try",
    { question, expect_unanswerable: expectUnanswerable },
    s,
  );

/** Queues a question for review; it still needs make eval-promote. */
export const addCandidate = (payload: CandidatePayload, s?: AbortSignal) =>
  postJson<CandidateQueued>("/api/eval/candidates", payload, s);

/**
 * POST a question and yield each server-sent event as it arrives.
 *
 * EventSource can't send a body, so this reads the SSE framing off a plain
 * streamed fetch: split on the blank line between events, take the `data:`
 * payload of each.
 */
export async function* askStream(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_URL}/api/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;

    let split = buffer.indexOf("\n\n");
    while (split !== -1) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const payload = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (payload) yield JSON.parse(payload) as StreamEvent;
      split = buffer.indexOf("\n\n");
    }
  }
}

/**
 * The dashboard payload, fetched at most once per page load.
 *
 * The hero and the analytics tab both need these numbers; caching the promise
 * rather than the value means concurrent callers share the same in-flight
 * request instead of racing two of them.
 */
let dashboardPromise: Promise<Dashboard> | null = null;

export function dashboardOnce(): Promise<Dashboard> {
  if (!dashboardPromise) {
    dashboardPromise = getDashboard().catch((err) => {
      dashboardPromise = null; // let a later mount retry
      throw err;
    });
  }
  return dashboardPromise;
}
