"use client";

import { useEffect, useState } from "react";
import { BarChart3, FileText, MessagesSquare, Table2 } from "lucide-react";
import { Chat } from "@/components/Chat";
import { Dashboard } from "@/components/Dashboard";
import { DataView } from "@/components/DataView";
import { DocumentsView } from "@/components/DocumentsView";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge, cx } from "@/components/ui";
import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

const TABS = [
  { id: "ask", label: "Ask", Icon: MessagesSquare },
  { id: "dashboard", label: "Dashboard", Icon: BarChart3 },
  { id: "data", label: "Data", Icon: Table2 },
  { id: "documents", label: "Documents", Icon: FileText },
] as const;

type TabId = (typeof TABS)[number]["id"];

function HealthPill({ health, offline }: { health: Health | null; offline: boolean }) {
  if (offline) {
    return (
      <Badge tone="warn">
        <span className="size-1.5 rounded-full bg-current" />
        API offline
      </Badge>
    );
  }
  if (!health) {
    return (
      <Badge tone="neutral">
        <span className="animate-dot size-1.5 rounded-full bg-current" />
        Connecting
      </Badge>
    );
  }
  if (!health.has_api_key) {
    return (
      <Badge tone="warn">
        <span className="size-1.5 rounded-full bg-current" />
        No API key
      </Badge>
    );
  }
  return (
    <Badge tone="accent" className="hidden sm:inline-flex">
      <span className="size-1.5 rounded-full bg-current" />
      <span className="font-mono text-[11px]">{health.llm_model}</span>
    </Badge>
  );
}

/**
 * Apple's segmented control: one pill slides between equal-width slots rather
 * than each tab painting its own background, so the selection reads as a
 * single object moving.
 */
function Segmented({
  active,
  onChange,
}: {
  active: TabId;
  onChange: (id: TabId) => void;
}) {
  const index = TABS.findIndex((t) => t.id === active);
  return (
    <div className="relative grid grid-cols-4 rounded-full bg-surface-2 p-1">
      <span
        aria-hidden
        className="absolute inset-y-1 left-1 w-[calc(25%-0.25rem)] rounded-full bg-elevated shadow-[var(--shadow-sm)] transition-transform duration-500 [transition-timing-function:var(--ease)]"
        style={{ transform: `translateX(calc(${index} * (100% + 0.333rem)))` }}
      />
      {TABS.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          aria-current={active === id ? "page" : undefined}
          className={cx(
            "relative z-10 flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5",
            "text-[13px] font-medium transition-colors duration-300",
            active === id ? "text-text" : "text-muted hover:text-text",
          )}
        >
          <Icon size={14} strokeWidth={2.1} />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

/** One tab's content: kept in the tree when inactive so it doesn't refetch. */
function Panel({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <div hidden={!active} className={cx(!active && "hidden", "animate-fade-up")}>
      {children}
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState<TabId>("ask");
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Panels mount on first visit and then stay mounted, hidden rather than
  // unmounted. Switching tabs would otherwise refetch every endpoint, replay
  // every reveal, and throw away the conversation.
  const [visited, setVisited] = useState<Set<TabId>>(() => new Set<TabId>(["ask"]));

  const show = (id: TabId) => {
    setTab(id);
    setVisited((v) => (v.has(id) ? v : new Set(v).add(id)));
    window.scrollTo({ top: 0 });
  };

  useEffect(() => {
    const ctrl = new AbortController();
    getHealth(ctrl.signal)
      .then(setHealth)
      .catch((e) => {
        if (e.name !== "AbortError") setOffline(true);
      });
    return () => ctrl.abort();
  }, []);

  // The nav only grows a hairline once the page has moved, so it floats
  // cleanly over the hero at rest.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const chatDisabled = offline || (health !== null && !health.has_api_key);
  const disabledReason = offline
    ? "Can't reach the backend. Start it with `make api` (FastAPI on port 8010)."
    : health && !health.has_api_key
      ? `No API key found for ${health.llm_provider}. Add one to .env and restart `
        + "the backend — the dashboard and data views work without it."
      : undefined;

  return (
    <div className="min-h-screen">
      <header
        className={cx(
          "sticky top-0 z-30 transition-shadow duration-500 [transition-timing-function:var(--ease)]",
          scrolled && "shadow-[0_1px_0_var(--hairline)]",
        )}
        style={{ background: "var(--nav-bg)", backdropFilter: "saturate(180%) blur(20px)" }}
      >
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
          <button
            type="button"
            onClick={() => show("ask")}
            className="flex shrink-0 items-center gap-2.5 text-left"
          >
            <span
              className="flex size-7 items-center justify-center rounded-lg"
              style={{
                background: "linear-gradient(140deg, var(--sql), var(--rag))",
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M3 12.5h4l2-5 3.5 10 2.5-7.5 1.5 2.5H21"
                  stroke="#fff"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="hidden text-[15px] font-semibold tracking-[-0.02em] md:block">
              Structured Data RAG
            </span>
          </button>

          <div className="mx-auto w-full max-w-md">
            <Segmented active={tab} onChange={show} />
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <HealthPill health={health} offline={offline} />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main>
        <Panel active={tab === "ask"}>
          <Chat disabled={chatDisabled} disabledReason={disabledReason} />
        </Panel>
        {visited.has("dashboard") && (
          <Panel active={tab === "dashboard"}>
            <div className="mx-auto max-w-6xl px-6">
              <Dashboard />
            </div>
          </Panel>
        )}
        {visited.has("data") && (
          <Panel active={tab === "data"}>
            <div className="mx-auto max-w-6xl px-6">
              <DataView />
            </div>
          </Panel>
        )}
        {visited.has("documents") && (
          <Panel active={tab === "documents"}>
            <div className="mx-auto max-w-6xl px-6">
              <DocumentsView />
            </div>
          </Panel>
        )}
      </main>

      <footer className="mt-8 border-t border-hairline py-8">
        <div className="mx-auto max-w-6xl px-6">
          <p className="t-caption text-center">
            54,966 admissions · 5 policy documents · SQLite, FAISS and
            all-MiniLM-L6-v2, orchestrated with LangChain.
          </p>
        </div>
      </footer>
    </div>
  );
}
