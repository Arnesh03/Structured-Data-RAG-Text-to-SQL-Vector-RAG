"use client";

import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type ReactNode,
} from "react";
import { Database, FileText } from "lucide-react";
import type { Route } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ── Visibility ────────────────────────────────────────────────────── */

/**
 * True once the element has been on screen at least once.
 *
 * An IntersectionObserver drives it, with a timer that measures the element
 * directly as a backstop: a renderer that is throttled or not painting (a
 * background tab, a slow first paint) can delay the observer's first record
 * indefinitely, and content above the fold must never be left invisible
 * waiting for it.
 */
function useInView(ref: React.RefObject<HTMLElement | null>) {
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    observer.observe(node);

    const timer = setTimeout(() => {
      const box = node.getBoundingClientRect();
      if (box.top < window.innerHeight && box.bottom > 0) {
        setInView(true);
        observer.disconnect();
      }
    }, 80);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [ref]);

  return inView;
}

/* ── Scroll reveal ─────────────────────────────────────────────────── */

/** Fades and lifts its children into place the first time they come into view. */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const shown = useInView(ref);

  return (
    <div
      ref={ref}
      className={cx("reveal", shown && "is-in", className)}
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}

/* ── Animated numerals ─────────────────────────────────────────────── */

const MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeMotion(onChange: () => void) {
  const mq = window.matchMedia(MOTION_QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

/** Reads the OS motion preference as an external store, so no effect mirrors it. */
function usePrefersReducedMotion() {
  return useSyncExternalStore(
    subscribeMotion,
    () => window.matchMedia(MOTION_QUERY).matches,
    () => false,
  );
}

/**
 * Counts up to `value` once visible. Eased rather than linear so the number
 * decelerates into its final state instead of stopping dead.
 *
 * Only the animation progress lives in state; the displayed figure is derived
 * during render, which keeps the reduced-motion path free of any state at all.
 */
export function CountUp({
  value,
  duration = 1400,
  format = (n: number) => Math.round(n).toLocaleString("en-US"),
  className,
}: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = usePrefersReducedMotion();
  const visible = useInView(ref);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (reduced || !visible) return;

    let frame = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / duration);
      setProgress(1 - Math.pow(1 - t, 3));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(frame);
  }, [duration, reduced, visible]);

  return (
    <span ref={ref} className={className}>
      {format(reduced ? value : value * progress)}
    </span>
  );
}

/* ── Surfaces ──────────────────────────────────────────────────────── */

export function Card({
  children,
  className,
  padded = true,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  hover?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-[18px] bg-surface shadow-[var(--shadow-sm)] ring-1 ring-hairline",
        padded && "p-6 sm:p-7",
        hover &&
          "transition duration-500 [transition-timing-function:var(--ease)] hover:-translate-y-1 hover:shadow-[var(--shadow-lg)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h3 className="t-headline">{title}</h3>
        {hint && <p className="mt-1.5 text-[15px] leading-snug text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

/* ── Badges ────────────────────────────────────────────────────────── */

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "sql" | "rag" | "warn";
  className?: string;
}) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    accent: "bg-accent-soft text-accent",
    sql: "bg-sql-soft text-sql",
    rag: "bg-rag-soft text-rag",
    warn: "bg-warn-soft text-warn",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5",
        "text-[12px] font-medium leading-none",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export const ROUTE_META: Record<
  Route,
  { label: string; blurb: string; Icon: typeof Database }
> = {
  sql: {
    label: "Text-to-SQL",
    blurb: "Queried the admissions table",
    Icon: Database,
  },
  rag: {
    label: "Vector RAG",
    blurb: "Retrieved from the policy documents",
    Icon: FileText,
  },
};

export function RouteBadge({ route, elapsed }: { route: Route; elapsed?: number }) {
  const { label, Icon } = ROUTE_META[route];
  return (
    <Badge tone={route}>
      <Icon size={12} strokeWidth={2.5} />
      {label}
      {elapsed !== undefined && (
        <span className="opacity-55 tabular-nums">{elapsed.toFixed(1)}s</span>
      )}
    </Badge>
  );
}

/* ── Loading & states ──────────────────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cx("shimmer rounded-[18px] bg-surface ring-1 ring-hairline", className)}
      aria-hidden
    />
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="mx-auto max-w-xl rounded-[18px] bg-surface px-6 py-5 text-center text-[15px] text-danger ring-1 ring-hairline"
    >
      {message}
    </div>
  );
}
