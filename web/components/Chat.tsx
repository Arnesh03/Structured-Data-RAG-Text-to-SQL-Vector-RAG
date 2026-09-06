"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Database, FileText, Square, Trash2 } from "lucide-react";
import { askStream, getExamples } from "@/lib/api";
import type { ExampleQuestion, Message, Route } from "@/lib/types";
import { Hero } from "./Hero";
import { MessageCard } from "./MessageCard";
import { Reveal, cx } from "./ui";

const newId = () => Math.random().toString(36).slice(2);

function ExampleGroup({
  route,
  questions,
  onPick,
  delay,
}: {
  route: Route;
  questions: string[];
  onPick: (q: string) => void;
  delay: number;
}) {
  const Icon = route === "sql" ? Database : FileText;
  return (
    <Reveal delay={delay}>
      <div
        className={cx(
          "mb-4 flex items-center gap-2 text-[13px] font-semibold",
          route === "sql" ? "text-sql" : "text-rag",
        )}
      >
        <Icon size={14} strokeWidth={2.4} />
        {route === "sql" ? "Text-to-SQL" : "Vector RAG"}
      </div>
      <div className="flex flex-col gap-2.5">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className={cx(
              "group rounded-2xl bg-surface px-5 py-4 text-left text-[15px] leading-snug",
              "text-muted ring-1 ring-hairline",
              "transition duration-500 [transition-timing-function:var(--ease)]",
              "hover:-translate-y-0.5 hover:text-text hover:shadow-[var(--shadow-md)]",
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </Reveal>
  );
}

export function Chat({
  disabled,
  disabledReason,
}: {
  disabled?: boolean;
  disabledReason?: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getExamples(ctrl.signal).then(setExamples).catch(() => {});
    return () => ctrl.abort();
  }, []);

  // Keep the newest turn in view as the answer streams in. The page itself
  // scrolls now, so this drives the window rather than an inner container.
  useEffect(() => {
    if (messages.length === 0) return;
    const thread = threadRef.current;
    if (!thread) return;
    const bottom = thread.getBoundingClientRect().bottom + window.scrollY;
    window.scrollTo({ top: bottom - window.innerHeight + 140, behavior: "smooth" });
  }, [messages]);

  // The composer grows with its content instead of scrolling internally.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy) return;

      const replyId = newId();
      setMessages((m) => [
        ...m,
        { id: newId(), role: "user", text },
        { id: replyId, role: "assistant", text: "", stage: "routing" },
      ]);
      setInput("");
      setBusy(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      // Every branch mutates the same placeholder message in place, so the
      // card fills in progressively instead of appearing all at once.
      const patch = (fn: (m: Message) => Message) =>
        setMessages((all) => all.map((m) => (m.id === replyId ? fn(m) : m)));

      try {
        for await (const ev of askStream(text, ctrl.signal)) {
          switch (ev.type) {
            case "stage":
              patch((m) => ({ ...m, stage: ev.stage }));
              break;
            case "route":
              patch((m) => ({ ...m, route: ev.route }));
              break;
            case "sql":
              patch((m) => ({ ...m, sql: ev.sql_query }));
              break;
            case "rows":
              patch((m) => ({
                ...m,
                columns: ev.columns,
                rows: ev.rows,
                rowCount: ev.row_count,
              }));
              break;
            case "sources":
              patch((m) => ({ ...m, sources: ev.sources, chunks: ev.chunks }));
              break;
            case "token":
              patch((m) => ({ ...m, text: m.text + ev.text }));
              break;
            case "done":
              patch((m) => ({
                ...m,
                text: ev.result.answer,
                elapsed: ev.result.elapsed,
                done: true,
              }));
              break;
            case "error":
              patch((m) => ({ ...m, error: ev.message, done: true }));
              break;
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          patch((m) => ({
            ...m,
            error:
              (err as Error).message ||
              "Could not reach the API. Is the backend running on port 8010?",
            done: true,
          }));
        } else {
          patch((m) => ({ ...m, done: true, text: m.text || "_Stopped._" }));
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
        inputRef.current?.focus();
      }
    },
    [busy],
  );

  const grouped = {
    sql: examples.filter((e) => e.route === "sql").slice(0, 4).map((e) => e.q),
    rag: examples.filter((e) => e.route === "rag").slice(0, 4).map((e) => e.q),
  };

  return (
    <div className="pb-4">
      {messages.length === 0 ? (
        <>
          <Hero />
          <div className="mx-auto mt-16 max-w-3xl px-6 sm:mt-24">
            <Reveal className="mb-10 text-center">
              <h2 className="t-headline">Start with one of these</h2>
              <p className="mt-2 text-[15px] text-muted">
                Watch the badge on the answer to see which pipeline took it.
              </p>
            </Reveal>
            <div className="grid gap-8 sm:grid-cols-2 sm:gap-6">
              <ExampleGroup route="sql" questions={grouped.sql} onPick={send} delay={0} />
              <ExampleGroup route="rag" questions={grouped.rag} onPick={send} delay={90} />
            </div>
          </div>
        </>
      ) : (
        <div ref={threadRef} className="mx-auto flex max-w-3xl flex-col gap-5 px-6 pt-8">
          {messages.map((m) => (
            <MessageCard key={m.id} message={m} />
          ))}
        </div>
      )}

      {/* Composer: sticks to the bottom of the viewport as the page scrolls. */}
      <div className="sticky bottom-0 z-20 mt-10 px-6 pb-5 pt-8">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 top-0 backdrop-blur-xl [mask-image:linear-gradient(to_bottom,transparent,black_38%)]"
          style={{ background: "linear-gradient(to bottom, transparent, var(--bg) 55%)" }}
        />
        <div className="relative mx-auto max-w-3xl">
          {disabled && disabledReason && (
            <p className="mb-3 rounded-2xl bg-warn-soft px-5 py-3.5 text-[14px] leading-snug text-warn">
              {disabledReason}
            </p>
          )}
          <div
            className={cx(
              "flex items-end gap-2 rounded-[26px] bg-surface p-2.5 pl-5",
              "shadow-[var(--shadow-lg)] ring-1 ring-hairline",
              "transition duration-300 [transition-timing-function:var(--ease)]",
              "focus-within:ring-2 focus-within:ring-accent",
            )}
          >
            <textarea
              ref={inputRef}
              value={input}
              rows={1}
              disabled={disabled}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder={
                disabled
                  ? "Set an API key to start asking"
                  : "Ask about conditions, billing, length of stay, or hospital policy…"
              }
              className="max-h-[200px] min-h-[28px] flex-1 resize-none self-center bg-transparent py-1.5 text-[17px] outline-none placeholder:text-faint disabled:cursor-not-allowed"
            />
            {messages.length > 0 && !busy && (
              <button
                type="button"
                onClick={() => setMessages([])}
                aria-label="Clear conversation"
                className="flex size-10 items-center justify-center rounded-full text-faint transition hover:bg-surface-2 hover:text-text"
              >
                <Trash2 size={17} />
              </button>
            )}
            <button
              type="button"
              onClick={busy ? () => abortRef.current?.abort() : () => send(input)}
              disabled={disabled || (!busy && !input.trim())}
              aria-label={busy ? "Stop" : "Send"}
              className={cx(
                "flex size-10 shrink-0 items-center justify-center rounded-full",
                "transition duration-300 [transition-timing-function:var(--ease)]",
                busy
                  ? "bg-surface-2 text-text hover:bg-surface-3"
                  : "bg-accent text-on-accent hover:brightness-110 disabled:opacity-25",
              )}
            >
              {busy ? <Square size={13} fill="currentColor" /> : <ArrowUp size={18} />}
            </button>
          </div>
          <p className="t-caption mt-3 text-center">
            Synthetic dataset for demonstration. Not medical advice.
          </p>
        </div>
      </div>
    </div>
  );
}
