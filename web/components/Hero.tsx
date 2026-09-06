"use client";

import { useEffect, useState } from "react";
import { dashboardOnce } from "@/lib/api";
import type { Kpis } from "@/lib/types";
import { CountUp, Reveal } from "./ui";
import { RouterDiagram } from "./RouterDiagram";

/** Soft colour wash behind the hero, drifting slowly so the page feels alive. */
function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="animate-drift absolute -top-40 left-1/2 size-[560px] -translate-x-[70%] rounded-full opacity-[0.28] blur-[110px] dark:opacity-[0.22]"
        style={{ background: "var(--sql)" }}
      />
      <div
        className="animate-drift absolute -top-24 left-1/2 size-[480px] translate-x-[10%] rounded-full opacity-[0.22] blur-[110px] dark:opacity-[0.18]"
        style={{ background: "var(--rag)", animationDelay: "-8s" }}
      />
    </div>
  );
}

function Stat({
  value,
  label,
  format,
}: {
  value: number;
  label: string;
  format?: (n: number) => string;
}) {
  return (
    <div className="text-center">
      <p className="t-numeral text-[clamp(1.75rem,3.4vw,2.75rem)]">
        <CountUp value={value} format={format} />
      </p>
      <p className="t-caption mt-1">{label}</p>
    </div>
  );
}

export function Hero() {
  const [kpis, setKpis] = useState<Kpis | null>(null);

  useEffect(() => {
    let live = true;
    dashboardOnce()
      .then((d) => live && setKpis(d.kpis))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  return (
    <div className="relative isolate">
      <Aurora />

      <div className="relative mx-auto max-w-4xl px-6 pb-6 pt-14 text-center sm:pt-20">
        <Reveal>
          <p className="t-eyebrow mb-5">Hybrid retrieval-augmented generation</p>
        </Reveal>

        <Reveal delay={80}>
          <h1 className="t-display text-balance">
            Two pipelines.
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(100deg, var(--sql), var(--rag) 90%)",
              }}
            >
              One question.
            </span>
          </h1>
        </Reveal>

        <Reveal delay={160}>
          <p className="t-intro mx-auto mt-6 max-w-xl text-balance">
            Ask about the numbers or ask about the rules. A router reads the
            question, picks the pipeline that can actually answer it, and shows
            you its work.
          </p>
        </Reveal>

        <Reveal delay={260} className="mt-10 sm:mt-14">
          <RouterDiagram />
        </Reveal>

        <Reveal delay={340}>
          <div className="mx-auto mt-10 grid max-w-2xl grid-cols-3 gap-6 border-t border-hairline pt-8 sm:mt-14">
            {kpis ? (
              <>
                <Stat value={kpis.total_admissions} label="Admissions indexed" />
                <Stat
                  value={kpis.total_billing}
                  label="Billing analysed"
                  format={(n) => `$${(n / 1e9).toFixed(2)}B`}
                />
                <Stat value={5} label="Policy documents" />
              </>
            ) : (
              <>
                <Stat value={0} label="Admissions indexed" />
                <Stat value={0} label="Billing analysed" format={() => "—"} />
                <Stat value={5} label="Policy documents" />
              </>
            )}
          </div>
        </Reveal>
      </div>
    </div>
  );
}
