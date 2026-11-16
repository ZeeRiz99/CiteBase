"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { SourceViewerBody } from "@/components/chat/source-viewer";
import { Button } from "@/components/ui/button";
import { useChunkContext } from "@/lib/chat";

/** Full-page source viewer (shareable link to a cited passage). */
export function SourcePageView({ chunkId }: { chunkId: string }) {
  const router = useRouter();
  const context = useChunkContext(chunkId);
  return (
    <div className="mx-auto grid max-w-3xl gap-5">
      <div className="grid gap-2">
        <Button variant="ghost" size="sm" className="w-fit" onClick={() => router.back()}>
          <ArrowLeft aria-hidden /> Back to answer
        </Button>
        {context.data ? (
          <div>
            <h1 className="text-2xl font-semibold text-navy-900">{context.data.document.title}</h1>
            <p className="text-sm text-muted-foreground">
              {context.data.document.file_ext === ".pdf" ? "Page" : "Section"} {context.data.chunk.page_start}
              {context.data.chunk.page_end !== context.data.chunk.page_start ? `–${context.data.chunk.page_end}` : ""}
              {context.data.chunk.section_title ? ` · ${context.data.chunk.section_title}` : ""}
            </p>
          </div>
        ) : null}
      </div>
      <SourceViewerBody chunkId={chunkId} />
    </div>
  );
}
