"use client";

import { FileText } from "lucide-react";

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { sourceLocation, type Source } from "@/lib/chat";
import { cn } from "@/lib/utils";

/** An inline [n] citation: hover or focus for a preview, click to open the passage. */
export function CitationChip({
  number,
  source,
  onOpen,
}: {
  number: number;
  source: Source | undefined;
  onOpen: (source: Source) => void;
}) {
  const available = source?.available ?? false;
  const label = source ? `Source ${number}: ${source.document_title}, ${source.location}` : `Source ${number}`;
  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          aria-label={label}
          disabled={!source}
          onClick={() => source && available && onOpen(source)}
          className={cn(
            "mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-full px-1.5 align-baseline text-[11px] leading-none font-semibold transition-colors",
            available
              ? "bg-teal-100 text-teal-700 hover:bg-teal-600 hover:text-white focus-visible:bg-teal-600 focus-visible:text-white"
              : "bg-muted text-muted-foreground",
          )}
        >
          {number}
        </button>
      </HoverCardTrigger>
      {source ? (
        <HoverCardContent className="w-80" side="top">
          <div className="grid gap-1.5">
            <p className="flex items-start gap-1.5 text-sm font-medium text-navy-900">
              <FileText className="mt-0.5 size-3.5 shrink-0 text-teal-700" aria-hidden />
              <span className="min-w-0">
                {source.document_title}
                <span className="block text-xs font-normal text-muted-foreground">
                  {sourceLocation(source)}
                </span>
              </span>
            </p>
            {available ? (
              <>
                <p className="line-clamp-5 text-xs leading-relaxed text-slate-body">{source.snippet}</p>
                <p className="text-xs text-teal-700">Click to open the passage</p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">This document was removed from the knowledge base.</p>
            )}
          </div>
        </HoverCardContent>
      ) : null}
    </HoverCard>
  );
}
