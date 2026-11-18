"use client";

import { AlertTriangle, ChevronLeft, ChevronRight, RotateCw, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ConfirmEmailNotice } from "@/components/app/confirm-email-notice";
import { EmptyDocumentsIllustration } from "@/components/brand/empty-documents";
import { DocumentActions } from "@/components/documents/document-actions";
import { StatusBadge } from "@/components/documents/status-badge";
import { UploadDropzone } from "@/components/documents/upload-dropzone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { needsEmailConfirmation, useMe } from "@/lib/auth";
import { useDocuments, type DocumentItem, type StatusFilter } from "@/lib/documents";
import { fileTypeLabel, formatBytes, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "processing", label: "Processing" },
  { value: "indexed", label: "Ready" },
  { value: "attention", label: "Needs attention" },
];

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function KnowledgeBaseView() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim(), 300);
  const { data, error, isPending, isFetching, refetch } = useDocuments({ q, status, page });

  const { data: me } = useMe();
  const isViewer = me?.role === "viewer"; // viewers read and ask; uploads need member (API-enforced)
  const unconfirmed = needsEmailConfirmation(me); // uploads wait for a confirmed email (API-enforced)
  const limits = data?.limits;
  const atLimit = limits ? limits.document_count >= limits.max_documents : false;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const filtered = q !== "" || status !== "all";

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="grid gap-1">
          <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">Knowledge base</h1>
          <p className="text-muted-foreground">
            Documents your answers come from.
            {limits ? ` ${limits.document_count} of ${limits.max_documents} documents used.` : ""}
          </p>
        </div>
      </div>

      {isViewer ? null : (
        <>
          {me && unconfirmed ? <ConfirmEmailNotice email={me.user.email} action="upload documents" /> : null}
          <UploadDropzone limits={limits} disabled={atLimit || unconfirmed} />
        </>
      )}
      {atLimit ? (
        <p className="text-sm text-warning" role="status">
          You have reached your workspace limit. Delete a document to upload another.
        </p>
      ) : null}

      <section className="grid gap-4" aria-label="Documents">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search by name"
              aria-label="Search documents by name"
              className="h-9 bg-white pl-9"
            />
          </div>
          <div role="radiogroup" aria-label="Filter by status" className="flex flex-wrap gap-1 rounded-lg bg-muted p-1">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                role="radio"
                aria-checked={status === f.value}
                onClick={() => {
                  setStatus(f.value);
                  setPage(1);
                }}
                className={cn(
                  "rounded-md px-3 py-1 text-sm font-medium transition-colors",
                  status === f.value ? "bg-white text-navy-900 shadow-soft" : "text-muted-foreground hover:text-navy-900",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          {isFetching && !isPending ? <span className="text-xs text-muted-foreground">Updating…</span> : null}
        </div>

        {error ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border bg-white p-10 text-center" role="alert">
            <AlertTriangle className="size-8 text-warning" aria-hidden />
            <p className="font-medium">We could not load your documents.</p>
            <Button variant="outline" onClick={() => refetch()}>
              <RotateCw aria-hidden /> Try again
            </Button>
          </div>
        ) : isPending ? (
          <TableSkeleton />
        ) : data.items.length === 0 ? (
          <EmptyState filtered={filtered} />
        ) : (
          <>
            <div className="overflow-hidden rounded-2xl border bg-white shadow-soft">
              <Table>
                <TableHeader>
                  <TableRow className="bg-navy-50/60 hover:bg-navy-50/60">
                    <TableHead className="pl-4">Name</TableHead>
                    <TableHead className="hidden md:table-cell">Type</TableHead>
                    <TableHead className="hidden md:table-cell">Size</TableHead>
                    <TableHead className="hidden lg:table-cell">Pages</TableHead>
                    <TableHead className="hidden sm:table-cell">Uploaded</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((doc) => (
                    <DocumentRow key={doc.id} doc={doc} />
                  ))}
                </TableBody>
              </Table>
            </div>
            {pages > 1 ? (
              <nav className="flex items-center justify-end gap-2" aria-label="Pagination">
                <span className="text-sm text-muted-foreground">
                  Page {page} of {pages}
                </span>
                <Button variant="outline" size="icon-sm" onClick={() => setPage((p) => p - 1)} disabled={page <= 1} aria-label="Previous page">
                  <ChevronLeft aria-hidden />
                </Button>
                <Button variant="outline" size="icon-sm" onClick={() => setPage((p) => p + 1)} disabled={page >= pages} aria-label="Next page">
                  <ChevronRight aria-hidden />
                </Button>
              </nav>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}

function DocumentRow({ doc }: { doc: DocumentItem }) {
  const v = doc.latest;
  const problem = v.status === "failed" || v.status === "needs_ocr";
  return (
    <TableRow>
      <TableCell className="pl-4 whitespace-normal sm:max-w-xs">
        <Link
          href={`/knowledge-base/${doc.id}`}
          className="block font-medium break-words text-navy-900 hover:text-teal-700 hover:underline sm:truncate"
        >
          {doc.title}
        </Link>
        {v.version_number > 1 ? <span className="text-xs text-muted-foreground">Version {v.version_number}</span> : null}
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">
        {fileTypeLabel(v.file_ext)}
        {v.ocr_pages > 0 ? (
          <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium" title="Text read with text recognition">
            OCR
          </span>
        ) : null}
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">{formatBytes(v.size_bytes)}</TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">{v.page_count ?? "—"}</TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">{formatDate(v.created_at)}</TableCell>
      <TableCell>
        {problem && v.error_message ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="rounded-full" aria-label={`${v.status}: ${v.error_message}`}>
                <StatusBadge status={v.status} code={v.error_code} />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">{v.error_message}</TooltipContent>
          </Tooltip>
        ) : (
          <StatusBadge status={v.status} code={v.error_code} />
        )}
      </TableCell>
      <TableCell>
        <DocumentActions document={doc} />
      </TableCell>
    </TableRow>
  );
}

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed bg-white px-6 py-12 text-center">
      <EmptyDocumentsIllustration className="h-24 w-32" />
      {filtered ? (
        <>
          <p className="font-medium text-navy-900">No documents match</p>
          <p className="text-sm text-muted-foreground">Try a different name or status filter.</p>
        </>
      ) : (
        <>
          <p className="font-medium text-navy-900">No documents yet</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Upload handbooks, policies or manuals above. Each one is read, split into passages and indexed so answers
            can cite it.
          </p>
        </>
      )}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="grid gap-2 rounded-2xl border bg-white p-4" aria-busy="true" aria-label="Loading documents">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="hidden h-4 w-16 md:block" />
          <Skeleton className="hidden h-4 w-20 sm:block" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}
