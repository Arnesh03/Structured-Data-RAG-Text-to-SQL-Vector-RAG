import type {
  Dashboard,
  ExampleQuestion,
  Health,
  PolicyDocument,
  PreprocessingReport,
  SchemaColumn,
  StreamEvent,
} from "./types";

/** The FastAPI backend. Override with NEXT_PUBLIC_API_URL for a remote host. */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8010";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${res.statusText}`);
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
