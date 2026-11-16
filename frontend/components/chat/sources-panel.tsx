"use client";

import { BookOpen, FileText } from "lucide-react";

import { sourceLocation, type Source } from "@/lib/chat";
import { cn } from "@/lib/utils";

/** Every passage the model saw for the selected answer: cited ones first, then the rest. */
export function SourcesPanel({ sources, onOpen }: { sources: Source[] | null; onOpen: (source: Source) => void }) {
  if (!sources || sources.length === 0) {
    return (
      <div className="grid justify-items-center gap-2 px-4 py-10 text-center">
        <BookOpen className="size-8 text-muted-foreground/60" aria-hidden />
        <p className="text-sm text-muted-foreground">
          {sources ? "No passages were used for this answer." : "Sources for an answer appear here."}
        </p>
      </div>
    );
  }
  const cited = sources.filter((s) => s.cited);
  const others = sources.filter((s) => !s.cited);
  return (
    <div className="grid gap-5">
      {cited.length ? <SourceGroup title="Cited in the answer" sources={cited} onOpen={onOpen} /> : null}
      {others.length ? (
        <SourceGroup title={cited.length ? "Also retrieved, not cited" : "Closest passages, not used"} sources={others} onOpen={onOpen} muted />
      ) : null}
    </div>
  );
}

function SourceGroup({
  title,
  sources,
  onOpen,
  muted,
}: {
  title: string;
  sources: Source[];
  onOpen: (source: Source) => void;
  muted?: boolean;
}) {
  return (
    <section className="grid gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      <ul className="grid gap-2">
        {sources.map((s) => (
          <li key={s.number}>
            <button
              type="button"
              disabled={!s.available}
              onClick={() => onOpen(s)}
              className={cn(
                "grid w-full gap-1.5 rounded-xl border bg-white p-3 text-left transition-colors hover:border-teal-500/60 disabled:cursor-not-allowed disabled:opacity-60",
                muted && "bg-white/60",
              )}
            >
              <span className="flex items-start gap-2">
                <span
                  className={cn(
                    "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                    s.cited ? "bg-teal-100 text-teal-700" : "bg-muted text-muted-foreground",
                  )}
                >
                  {s.number}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1 text-sm font-medium text-navy-900">
                    <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="truncate">{s.document_title}</span>
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {sourceLocation(s)}
                  </span>
                </span>
              </span>
              <span className="line-clamp-4 text-xs leading-relaxed text-slate-body">
                {s.available ? s.snippet : "This document was removed from the knowledge base."}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
