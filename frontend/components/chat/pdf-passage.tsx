"use client";

import { ChevronLeft, ChevronRight, Crosshair } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { escapeHtml, findPassage, type PassageMatch } from "@/lib/highlight";
import { cn } from "@/lib/utils";

// Must be set in the module that renders react-pdf components (see the react-pdf README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export type PdfPassageProps = {
  fileUrl: string;
  passage: string;
  pageStart: number;
  pageEnd: number;
  onMatch?: (match: { page: number; matched: boolean } | null) => void;
};

/** One PDF page at a time, opened at the cited page, with the passage highlighted. */
export default function PdfPassage({ fileUrl, passage, pageStart, pageEnd, onMatch }: PdfPassageProps) {
  const [page, setPage] = useState(pageStart);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [width, setWidth] = useState<number>();
  const [match, setMatch] = useState<PassageMatch | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const inRange = page >= pageStart && page <= pageEnd;

  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  const goTo = (next: number) => {
    setMatch(null);
    onMatch?.(null);
    setPage(next);
  };

  const renderText = useCallback(
    ({ str, itemIndex }: { str: string; itemIndex: number }) =>
      match?.items.has(itemIndex) ? `<mark class="cb-hl">${escapeHtml(str)}</mark>` : escapeHtml(str),
    [match],
  );

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon-sm" onClick={() => goTo(page - 1)} disabled={page <= 1} aria-label="Previous page">
          <ChevronLeft aria-hidden />
        </Button>
        <span className="text-sm tabular-nums text-muted-foreground" aria-live="polite">
          Page {page}
          {numPages ? ` of ${numPages}` : ""}
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => goTo(page + 1)}
          disabled={numPages !== null && page >= numPages}
          aria-label="Next page"
        >
          <ChevronRight aria-hidden />
        </Button>
        {!inRange ? (
          <Button variant="ghost" size="sm" onClick={() => goTo(pageStart)}>
            <Crosshair aria-hidden /> Back to cited page
          </Button>
        ) : null}
      </div>
      <div
        ref={boxRef}
        className={cn(
          "overflow-hidden rounded-lg border bg-white",
          inRange && match && !match.matched && "ring-2 ring-teal-500 ring-offset-2",
        )}
      >
        <Document
          file={fileUrl}
          suspense={false}
          onLoadSuccess={(doc) => setNumPages(doc.numPages)}
          loading={<Skeleton className="aspect-[1/1.3] w-full" />}
          error={<p className="p-6 text-sm text-destructive">This PDF could not be displayed. Download it instead.</p>}
        >
          <Page
            key={page}
            pageNumber={page}
            width={width}
            suspense={false}
            renderAnnotationLayer={false}
            customTextRenderer={renderText}
            loading={<Skeleton className="aspect-[1/1.3] w-full" />}
            onGetTextSuccess={(content) => {
              if (!inRange) return;
              const strings = content.items.map((item) => ("str" in item ? item.str : ""));
              const found = findPassage(strings, passage);
              setMatch(found);
              onMatch?.({ page, matched: found.matched });
            }}
            onRenderTextLayerSuccess={() => {
              boxRef.current?.querySelector("mark.cb-hl")?.scrollIntoView({ block: "center" });
            }}
          />
        </Document>
      </div>
    </div>
  );
}
