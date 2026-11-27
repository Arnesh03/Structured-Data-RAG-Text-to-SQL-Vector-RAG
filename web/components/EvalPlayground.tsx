"use client";

import { useRef, useState } from "react";
import { CornerDownLeft, Loader2, Plus, TriangleAlert } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardHeader, RouteBadge, cx } from "@/components/ui";
import { addCandidate, tryQuestion } from "@/lib/api";
import { TONE_BG, TONE_TEXT, label, toneOf } from "@/lib/metrics";
import type { CandidatePayload, EvalDataset, Route, TryResult } from "@/lib/types";

const SUGGESTIONS = [
  "What is the average billing amount for diabetes admissions?",
  "Who qualifies for financial assistance?",
  "Which hospital treated the most cancer patients?",
  "What are the visiting hours?",
];

/* ── Grades ────────────────────────────────────────────────────────── */

function GradeChips({ grades }: { grades: Record<string, number> }) {
  const entries = Object.entries(grades);
  if (entries.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([metric, value]) => {
        const tone = toneOf(metric, value);
        return (
          <span
            key={metric}
            className={cx(
              "rounded-full px-2.5 py-1 text-[12px] font-medium",
              TONE_BG[tone],
              TONE_TEXT[tone],
            )}
          >
            {label(metric)} {value >= 1 ? "pass" : value <= 0 ? "fail" : value.toFixed(2)}
          </span>
        );
      })}
    </div>
  );
}

/* ── Save to the review queue ──────────────────────────────────────── */

/**
 * Turns an ad-hoc question into a candidate.
 *
 * The ground-truth fields are pre-filled with what the pipeline just produced
 * because that is the convenient starting point, NOT because it is ground
 * truth. Accepting them unchanged creates a question the system passes by
 * construction, which is why nothing written here skips the review queue.
 */
function SaveForm({
  result,
  sources,
  onDone,
}: {
  result: TryResult;
  sources: string[];
  onDone: (message: string) => void;
}) {
  const [route, setRoute] = useState<Route>(result.route ?? "rag");
  const [answerable, setAnswerable] = useState(!result.expected_unanswerable);
  const [category, setCategory] = useState(
    result.expected_unanswerable ? "unanswerable" : "from_playground",
  );
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [goldSql, setGoldSql] = useState(result.sql_query ?? "");
  const [docs, setDocs] = useState<string[]>(result.sources);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const toggleDoc = (file: string) =>
    setDocs((current) =>
      current.includes(file) ? current.filter((d) => d !== file) : [...current, file],
    );

  const save = async () => {
    setSaving(true);
    setError("");
    const payload: CandidatePayload = {
      question: result.question,
      route_label: route,
      category: category.trim() || "from_playground",
      difficulty,
      answerable,
      gold_sql: answerable && route === "sql" ? goldSql.trim() || null : null,
      gold_doc_ids: answerable && route === "rag" ? docs : null,
      gold_answer: null,
      notes: "queued from the Evals playground",
    };
    try {
      const queued = await addCandidate(payload);
      onDone(`Queued as ${queued.id} — ${queued.pending} awaiting review.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const field = "rounded-[10px] bg-surface-2 px-3 py-2 text-[14px] ring-1 ring-hairline";

  return (
    <div className="mt-5 border-t border-hairline pt-5">
      <p className="flex items-start gap-2 rounded-[12px] bg-warn-soft p-3 text-[13px] leading-relaxed text-warn">
        <TriangleAlert size={15} className="mt-0.5 shrink-0" />
        <span>
          These are pre-filled with what the pipeline just answered. Accepting
          them unchanged makes a question it passes by construction — correct
          them against the source, not against the output.
        </span>
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="t-caption">Correct route</span>
          <select
            value={route}
            onChange={(e) => setRoute(e.target.value as Route)}
            className={field}
          >
            <option value="sql">sql — the admissions table</option>
            <option value="rag">rag — the policy documents</option>
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="t-caption">Category</span>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={field}
            placeholder="aggregate_with_filter"
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="t-caption">Difficulty</span>
          <select
            value={difficulty}
            onChange={(e) =>
              setDifficulty(e.target.value as "easy" | "medium" | "hard")
            }
            className={field}
          >
            <option value="easy">easy</option>
            <option value="medium">medium</option>
            <option value="hard">hard</option>
          </select>
        </label>

        <label className="flex items-center gap-2.5 self-end pb-2">
          <input
            type="checkbox"
            checked={!answerable}
            onChange={(e) => setAnswerable(!e.target.checked)}
            className="size-4 accent-[var(--accent)]"
          />
          <span className="text-[14px]">
            Unanswerable
            <span className="t-caption block">no answer exists in the corpus</span>
          </span>
        </label>
      </div>

      {answerable && route === "sql" && (
        <label className="mt-3 flex flex-col gap-1.5">
          <span className="t-caption">
            Gold SQL — must return the rows that answer the question
          </span>
          <textarea
            value={goldSql}
            onChange={(e) => setGoldSql(e.target.value)}
            rows={3}
            spellCheck={false}
            className={cx(field, "resize-y font-mono text-[12.5px]")}
          />
        </label>
      )}

      {answerable && route === "rag" && (
        <div className="mt-3">
          <span className="t-caption">
            Documents that contain the answer — tick every one
          </span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {sources.map((file) => (
              <button
                key={file}
                type="button"
                onClick={() => toggleDoc(file)}
                className={cx(
                  "rounded-full px-3 py-1.5 font-mono text-[12px] transition-colors duration-200",
                  docs.includes(file)
                    ? "bg-accent text-on-accent"
                    : "bg-surface-2 text-muted hover:text-text",
                )}
              >
                {file}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-[13px] text-danger">{error}</p>}

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="mt-4 inline-flex items-center gap-2 rounded-full bg-text px-4 py-2 text-[13px] font-medium text-bg disabled:opacity-50"
      >
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
        Queue for review
      </button>
    </div>
  );
}

/* ── Result ────────────────────────────────────────────────────────── */

function Result({
  result,
  sources,
}: {
  result: TryResult;
  sources: string[];
}) {
  const [saving, setSaving] = useState(false);
  const [queued, setQueued] = useState("");

  return (
    <div className="mt-5 border-t border-hairline pt-5">
      <div className="flex flex-wrap items-center gap-2">
        {result.route && <RouteBadge route={result.route} elapsed={result.elapsed} />}
        {result.fallback_used ? (
          <span className="rounded-full bg-warn-soft px-2.5 py-1 text-[12px] font-medium text-warn">
            keyword fallback fired
          </span>
        ) : (
          <span className="t-caption">router: LLM</span>
        )}
        {result.keyword_route && result.keyword_route !== result.route && (
          <span className="t-caption">
            heuristic would have said{" "}
            <span className="font-mono">{result.keyword_route}</span>
          </span>
        )}
      </div>

      <div className="mt-3">
        <GradeChips grades={result.grades} />
        {result.judge_note && (
          <p className="t-caption mt-2 italic">judge: {result.judge_note}</p>
        )}
      </div>

      {/* The pipeline answers in markdown, same as the chat does. */}
      <div className="prose-answer mt-4 rounded-[12px] bg-surface-2 p-4">
        {result.answer ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
        ) : (
          "(no answer)"
        )}
      </div>

      {result.sql_query && (
        <div className="mt-3">
          <p className="t-caption mb-1.5">Generated SQL</p>
          <pre className="overflow-x-auto rounded-[12px] bg-surface-2 p-3 font-mono text-[12.5px] leading-relaxed">
            {result.sql_query}
          </pre>
          {result.rows.length > 0 && (
            <p className="t-caption mt-1.5">
              returned {result.rows.length} row{result.rows.length === 1 ? "" : "s"}
            </p>
          )}
        </div>
      )}

      {result.chunks.length > 0 && (
        <div className="mt-3">
          <p className="t-caption mb-1.5">
            Retrieved {result.chunks.length} chunk
            {result.chunks.length === 1 ? "" : "s"} from{" "}
            {result.sources.join(", ")}
          </p>
          <div className="flex flex-col gap-1.5">
            {result.chunks.map((chunk, i) => (
              <details
                key={`${chunk.file}-${i}`}
                className="rounded-[12px] bg-surface-2 p-3 text-[13px]"
              >
                <summary className="cursor-pointer font-mono text-[12px] text-muted">
                  {i + 1}. {chunk.file}
                </summary>
                <p className="mt-2 leading-relaxed">{chunk.text}</p>
              </details>
            ))}
          </div>
        </div>
      )}

      {queued ? (
        <p className="mt-5 rounded-[12px] bg-positive-soft p-3 text-[13px] text-positive">
          {queued} Review it in{" "}
          <code className="font-mono">evalkit/golden/candidates.jsonl</code>, then
          run <code className="font-mono">make eval-promote</code>.
        </p>
      ) : saving ? (
        <SaveForm result={result} sources={sources} onDone={setQueued} />
      ) : (
        <button
          type="button"
          onClick={() => setSaving(true)}
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-surface-2 px-4 py-2 text-[13px] font-medium text-muted transition-colors hover:text-text"
        >
          <Plus size={14} />
          Add this to the golden set
        </button>
      )}
    </div>
  );
}

/* ── The playground ────────────────────────────────────────────────── */

export function EvalPlayground({ dataset }: { dataset: EvalDataset | null }) {
  const [question, setQuestion] = useState("");
  const [unanswerable, setUnanswerable] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<TryResult | null>(null);
  const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null);

  const run = async () => {
    const q = question.trim();
    if (!q || running) return;

    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;

    setRunning(true);
    setError("");
    setResult(null);
    try {
      setResult(await tryQuestion(q, unanswerable, ctrl.signal));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Try a question"
        hint="Runs through the live pipeline and grades what can be graded without ground truth. Nothing here is recorded as a run."
      />

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void run();
            }
          }}
          placeholder="Ask anything the pipeline should be able to answer…"
          className="flex-1 rounded-[12px] bg-surface-2 px-4 py-3 text-[15px] ring-1 ring-hairline focus:ring-accent"
        />
        <button
          type="button"
          onClick={() => void run()}
          disabled={running || !question.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-[12px] bg-accent px-5 py-3 text-[14px] font-medium text-on-accent transition-opacity disabled:opacity-40"
        >
          {running ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <CornerDownLeft size={15} />
          )}
          {running ? "Running" : "Run"}
        </button>
      </div>

      <label className="mt-3 flex items-center gap-2.5">
        <input
          type="checkbox"
          checked={unanswerable}
          onChange={(e) => setUnanswerable(e.target.checked)}
          className="size-4 accent-[var(--accent)]"
        />
        <span className="text-[13.5px] text-muted">
          I expect this to be unanswerable
          <span className="t-caption block">
            grades whether it declines instead of whether it is faithful
          </span>
        </span>
      </label>

      {!result && !running && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setQuestion(suggestion)}
              className="rounded-full bg-surface-2 px-3 py-1.5 text-left text-[12.5px] text-muted transition-colors hover:text-text"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="mt-4 rounded-[12px] bg-danger-soft p-3 text-[13px] text-danger">
          {error}
        </p>
      )}

      {result && <Result result={result} sources={dataset?.sources ?? []} />}
    </Card>
  );
}
