"use client";

import { Download, ExternalLink, FileWarning, History } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";

import { TextPassage } from "@/components/chat/text-passage";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, isApiError } from "@/lib/api";
import { sourceLocation, useChunkContext, type ChunkContext, type Source } from "@/lib/chat";
import { fileTypeLabel, IMAGE_EXTS } from "@/lib/format";

// pdf.js needs the browser (canvas, workers): never rendered on the server.
const PdfPassage = dynamic(() => import("@/components/chat/pdf-passage"), {
  ssr: false,
  loading: () => <Skeleton className="aspect-[1/1.3] w-full" />,
});

export function fileUrl(context: ChunkContext) {
  return `/api/v1/documents/${context.document.id}/file?version_id=${context.document.version_id}`;
}

export function SourceViewerBody({ chunkId }: { chunkId: string }) {
  const query = useChunkContext(chunkId);
  const [pdfMatch, setPdfMatch] = useState<{ page: number; matched: boolean } | null>(null);

  if (query.isPending) {
    return (
      <div className="grid gap-3" aria-busy="true">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (query.isError) {
    const gone = isApiError(query.error) && query.error.status === 404;
    return (
      <Alert>
        <FileWarning aria-hidden />
        <AlertDescription>
          {gone ? "This passage is no longer available: its document was deleted." : errorMessage(query.error)}
        </AlertDescription>
      </Alert>
    );
  }

  const context = query.data;
  const isPdf = context.document.file_ext === ".pdf";
  const isImage = IMAGE_EXTS.has(context.document.file_ext);
  const scanned = context.document.ocr_pages > 0;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" asChild>
          <a href={fileUrl(context)} target="_blank" rel="noopener">
            <Download aria-hidden /> {isPdf || isImage ? "Open original" : `Download ${fileTypeLabel(context.document.file_ext)}`}
          </a>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/knowledge-base/${context.document.id}`}>
            <ExternalLink aria-hidden /> Document details
          </Link>
        </Button>
      </div>

      {!context.document.is_current ? (
        <Alert>
          <History aria-hidden />
          <AlertDescription>
            This passage is from version {context.document.version_number}. The document has been updated since this
            answer was written.
          </AlertDescription>
        </Alert>
      ) : null}

      {isPdf ? (
        <>
          <PdfPassage
            fileUrl={fileUrl(context)}
            passage={context.chunk.text}
            pageStart={context.chunk.page_start}
            pageEnd={context.chunk.page_end}
            onMatch={setPdfMatch}
          />
          {pdfMatch && !pdfMatch.matched ? (
            <p className="text-sm text-muted-foreground" role="status">
              {scanned
                ? "This page is a scan, so the lines cannot be marked on the image. The cited passage, as read by text recognition, is shown below."
                : "The exact lines could not be pinpointed on this page (the PDF's text layout differs). The cited passage is shown below."}
            </p>
          ) : null}
          <details className="rounded-lg border bg-muted/40 p-3" open={pdfMatch?.matched === false}>
            <summary className="cursor-pointer text-sm font-medium text-navy-900">Cited passage as text</summary>
            <div className="mt-3">
              <TextPassage context={context} unitLabel="Page" />
            </div>
          </details>
        </>
      ) : isImage ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API file, not a static asset */}
          <img src={fileUrl(context)} alt={`Original image: ${context.document.title}`} className="w-full rounded-lg border bg-white" />
          <p className="text-sm text-muted-foreground">Text read from the image by text recognition:</p>
          <TextPassage context={context} unitLabel="Page" />
        </>
      ) : (
        <TextPassage context={context} unitLabel="Section" />
      )}
    </div>
  );
}

/** Side sheet opened from a citation or the sources panel. */
export function SourceSheet({ source, onClose }: { source: Source | null; onClose: () => void }) {
  return (
    <Sheet open={source !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto data-[side=right]:sm:max-w-2xl">
        {source ? (
          <>
            <SheetHeader className="border-b">
              <SheetTitle className="pr-8">
                <span className="mr-2 inline-flex size-6 items-center justify-center rounded-full bg-teal-100 text-xs font-semibold text-teal-700">
                  {source.number}
                </span>
                {source.document_title}
              </SheetTitle>
              <SheetDescription>
                {sourceLocation(source)}
              </SheetDescription>
            </SheetHeader>
            <div className="p-4">
              {source.chunk_id && source.available ? (
                <SourceViewerBody chunkId={source.chunk_id} />
              ) : (
                <p className="text-sm text-muted-foreground">This document was removed from the knowledge base.</p>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
