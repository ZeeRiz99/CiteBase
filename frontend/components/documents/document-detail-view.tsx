"use client";

import { AlertTriangle, ArrowLeft, FileText, RotateCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DocumentActions } from "@/components/documents/document-actions";
import { StatusBadge } from "@/components/documents/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api";
import { IN_PROGRESS, useChunks, useDocument, type DocumentDetail } from "@/lib/documents";
import { fileTypeLabel, formatBytes, formatDateTime } from "@/lib/format";

export function DocumentDetailView({ id }: { id: string }) {
  const { data: doc, error, isPending, refetch } = useDocument(id);

  if (isPending) return <DetailSkeleton />;
  if (error) {
    const missing = isApiError(error) && error.status === 404;
    return (
      <div className="grid justify-items-start gap-4" role="alert">
        <BackLink />
        <h1 className="text-2xl font-semibold">{missing ? "Document not found" : "We could not load this document"}</h1>
        <p className="text-muted-foreground">
          {missing ? "It may have been deleted, or it belongs to another workspace." : "Check your connection and try again."}
        </p>
        {!missing ? (
          <Button variant="outline" onClick={() => refetch()}>
            <RotateCw aria-hidden /> Try again
          </Button>
        ) : null}
      </div>
    );
  }

  const v = doc.latest;
  return (
    <div className="grid gap-8">
      <div className="grid gap-4">
        <BackLink />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="grid min-w-0 gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="truncate text-2xl font-semibold text-navy-900 sm:text-3xl">{doc.title}</h1>
              <StatusBadge status={v.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {v.original_filename} · {fileTypeLabel(v.file_ext)} · {formatBytes(v.size_bytes)}
              {v.page_count ? ` · ${v.page_count} pages` : ""}
            </p>
          </div>
          <DocumentActions document={doc} variant="buttons" afterDelete="/knowledge-base" />
        </div>
      </div>

      {v.status === "failed" || v.status === "needs_ocr" ? (
        <Alert variant={v.status === "failed" ? "destructive" : "default"} className={v.status === "needs_ocr" ? "border-amber-200 bg-amber-50" : undefined}>
          <AlertTriangle aria-hidden />
          <AlertTitle>{v.status === "failed" ? "Processing failed" : "Text recognition needed"}</AlertTitle>
          <AlertDescription>
            {v.error_message}
            {doc.has_current_version ? " The previous version is still being used for answers." : ""}
          </AlertDescription>
        </Alert>
      ) : null}
      {IN_PROGRESS.has(v.status) && doc.has_current_version ? (
        <Alert>
          <AlertTitle>A new version is processing</AlertTitle>
          <AlertDescription>Answers keep using the previous version until this one is ready.</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="shadow-soft lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm">
              <Meta label="Uploaded" value={formatDateTime(v.created_at)} />
              <Meta label="Indexed" value={v.indexed_at ? formatDateTime(v.indexed_at) : "Not yet"} />
              <Meta label="Passages" value={v.chunk_count ? String(v.chunk_count) : "—"} />
              <Meta label="Version" value={`${v.version_number}${v.is_current ? " (live)" : ""}`} />
            </dl>
          </CardContent>
        </Card>
        <VersionsCard doc={doc} />
      </div>

      <ChunksCard id={doc.id} enabled={doc.has_current_version} />
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-navy-900">{value}</dd>
    </div>
  );
}

function VersionsCard({ doc }: { doc: DocumentDetail }) {
  return (
    <Card className="shadow-soft lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">Versions</CardTitle>
        <CardDescription>Uploading a new version keeps the old one live until the new one is ready.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-2">
          {doc.versions.map((version) => (
            <li key={version.id} className="flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2 text-sm">
              <span className="font-medium text-navy-900">v{version.version_number}</span>
              <span className="min-w-0 flex-1 truncate text-muted-foreground">{version.original_filename}</span>
              <span className="text-muted-foreground">{formatDateTime(version.created_at)}</span>
              {version.is_current ? (
                <span className="rounded-full bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">Live</span>
              ) : null}
              <StatusBadge status={version.status} />
              <a
                href={`/api/v1/documents/${doc.id}/file?version_id=${version.id}`}
                className="text-xs font-medium text-teal-700 hover:underline"
              >
                Download
              </a>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function ChunksCard({ id, enabled }: { id: string; enabled: boolean }) {
  const [page, setPage] = useState(1);
  const { data, isPending } = useChunks(id, page, enabled);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <Card className="shadow-soft">
      <CardHeader>
        <CardTitle className="text-base">Indexed passages</CardTitle>
        <CardDescription>
          How this document was split for search. Answers cite these passages by page or section.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {!enabled ? (
          <p className="text-sm text-muted-foreground">Passages appear here once the document is ready.</p>
        ) : isPending ? (
          <Skeleton className="h-24" />
        ) : data && data.items.length > 0 ? (
          <>
            <ol className="grid gap-3">
              {data.items.map((chunk) => (
                <li key={chunk.id} className="rounded-xl border bg-navy-50/40 p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <FileText className="size-3.5" aria-hidden />
                    <span className="font-medium text-navy-900">#{chunk.chunk_index + 1}</span>
                    <span>
                      {chunk.section_title
                        ? chunk.section_title
                        : chunk.page_start === chunk.page_end
                          ? `Page ${chunk.page_start}`
                          : `Pages ${chunk.page_start}–${chunk.page_end}`}
                    </span>
                    <span className="ml-auto">{chunk.token_count} tokens</span>
                  </div>
                  <p className="line-clamp-6 text-sm whitespace-pre-line text-slate-body">{chunk.text}</p>
                </li>
              ))}
            </ol>
            {pages > 1 ? (
              <div className="flex items-center justify-end gap-2">
                <span className="text-sm text-muted-foreground">
                  {page} / {pages}
                </span>
                <Button variant="outline" size="sm" onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" onClick={() => setPage((p) => p + 1)} disabled={page >= pages}>
                  Next
                </Button>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No passages.</p>
        )}
      </CardContent>
    </Card>
  );
}

function BackLink() {
  return (
    <Link href="/knowledge-base" className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-navy-900">
      <ArrowLeft className="size-4" aria-hidden /> Knowledge base
    </Link>
  );
}

function DetailSkeleton() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-label="Loading document">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-8 w-72" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-40" />
        <Skeleton className="h-40 lg:col-span-2" />
      </div>
    </div>
  );
}
