"use client";

import { useEffect, useRef } from "react";

import type { ChunkContext } from "@/lib/chat";

const CONTEXT_CHARS = 900; // text shown around the passage on neighbouring sections

type Segment = { text: string; highlight: boolean };

/**
 * The cited passage in its surrounding text, highlighted by the exact offsets stored at
 * ingestion (char_start in page_start, char_end in page_end). Used for DOCX, Markdown and text
 * files, and as the fallback beside a PDF page.
 */
export function passageSegments(context: ChunkContext): { page: number; heading: string | null; segments: Segment[] }[] {
  const { chunk } = context;
  return context.pages.map((page) => {
    const { text } = page;
    if (page.page_number < chunk.page_start) {
      return { page: page.page_number, heading: page.heading_path, segments: [{ text: tail(text), highlight: false }] };
    }
    if (page.page_number > chunk.page_end) {
      return { page: page.page_number, heading: page.heading_path, segments: [{ text: head(text), highlight: false }] };
    }
    const start = page.page_number === chunk.page_start ? clamp(chunk.char_start, text.length) : 0;
    const end = page.page_number === chunk.page_end ? clamp(chunk.char_end, text.length) : text.length;
    const segments: Segment[] = [];
    if (start > 0) segments.push({ text: tail(text.slice(0, start)), highlight: false });
    segments.push({ text: text.slice(start, Math.max(start, end)), highlight: true });
    if (end < text.length) segments.push({ text: head(text.slice(end)), highlight: false });
    return { page: page.page_number, heading: page.heading_path, segments };
  });
}

function clamp(n: number, max: number) {
  return Math.min(Math.max(n, 0), max);
}

function head(text: string) {
  return text.length > CONTEXT_CHARS ? `${text.slice(0, CONTEXT_CHARS).trimEnd()} …` : text;
}

function tail(text: string) {
  return text.length > CONTEXT_CHARS ? `… ${text.slice(-CONTEXT_CHARS).trimStart()}` : text;
}

export function TextPassage({ context, unitLabel }: { context: ChunkContext; unitLabel: string }) {
  const markRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center" });
  }, [context.chunk.id]);

  const blocks = passageSegments(context);
  const firstPage = blocks.find((b) => b.segments.some((s) => s.highlight))?.page;
  return (
    <div className="grid gap-4">
      {blocks.map(({ page, heading, segments }) => (
        <section key={page} aria-label={`${unitLabel} ${page}`} className="grid gap-1">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {unitLabel} {page}
            {heading ? ` · ${heading}` : ""}
          </p>
          <p className="text-sm leading-7 whitespace-pre-wrap text-slate-body">
            {segments.map((segment, i) => {
              if (!segment.highlight) return <span key={i}>{segment.text}</span>;
              const ref = page === firstPage ? markRef : undefined;
              return (
                <mark key={i} ref={ref} className="rounded-sm bg-teal-100 px-0.5 text-navy-900 ring-1 ring-teal-500/40">
                  {segment.text}
                </mark>
              );
            })}
          </p>
        </section>
      ))}
    </div>
  );
}
