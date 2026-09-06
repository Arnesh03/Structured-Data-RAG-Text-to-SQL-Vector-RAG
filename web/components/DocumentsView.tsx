"use client";

import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { getDocuments } from "@/lib/api";
import type { PolicyDocument } from "@/lib/types";
import { Badge, Card, ErrorNote, Reveal, Skeleton } from "./ui";

export function DocumentsView() {
  const [docs, setDocs] = useState<PolicyDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getDocuments(ctrl.signal)
      .then(setDocs)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, []);

  if (error) {
    return <div className="py-24"><ErrorNote message={`Could not load documents: ${error}`} /></div>;
  }

  if (!docs) {
    return (
      <div className="grid gap-5 py-16 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    );
  }

  return (
    <div className="pb-10">
      <section className="pt-14 sm:pt-20">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center sm:mb-16">
          <p className="t-eyebrow mb-3">The corpus</p>
          <h2 className="t-title text-balance">What the database can&rsquo;t tell you</h2>
          <p className="t-intro mt-4">
            Rules, protocols and rights live in documents, not columns. These
            five are rendered to PDF, chunked, embedded locally and indexed in
            FAISS — so retrieval exercises real PDF parsing.
          </p>
        </Reveal>
      </section>

      <div className="grid gap-5 md:grid-cols-2">
        {docs.map((doc, i) => (
          <Reveal key={doc.file} delay={(i % 2) * 80}>
            <Card hover className="h-full">
              <div className="mb-5 flex items-start gap-4">
                <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-rag-soft text-rag">
                  <FileText size={18} strokeWidth={2} />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="t-headline text-balance">{doc.title}</h3>
                  <p className="mt-1 font-mono text-[12px] text-faint">{doc.file}</p>
                </div>
                <Badge tone="rag">{doc.sections.length}</Badge>
              </div>
              <ul className="flex flex-col gap-2.5">
                {doc.sections.map((s) => (
                  <li key={s} className="flex items-start gap-2.5 text-[15px] leading-snug text-muted">
                    <span className="mt-[9px] size-1 shrink-0 rounded-full bg-rag" />
                    {s}
                  </li>
                ))}
              </ul>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
