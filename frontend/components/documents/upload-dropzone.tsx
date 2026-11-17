"use client";

import { CheckCircle2, FileUp, Loader2, UploadCloud, X, XCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useId, useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { errorMessage, isApiError } from "@/lib/api";
import { precheckFile, uploadDocument, useInvalidateDocuments, type Limits } from "@/lib/documents";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

type Item = {
  key: string;
  name: string;
  size: number;
  state: "uploading" | "done" | "error";
  progress: number;
  error?: string;
  duplicateId?: string;
  documentId?: string;
};

const CONCURRENCY = 2;

export function UploadDropzone({ limits, disabled }: { limits: Limits | undefined; disabled?: boolean }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const invalidate = useInvalidateDocuments();

  const update = useCallback((key: string, patch: Partial<Item>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
  }, []);

  const start = useCallback(
    async (files: File[]) => {
      if (!limits || files.length === 0) return;
      const queue: { file: File; key: string }[] = [];
      const added: Item[] = files.map((file) => {
        const key = `${file.name}-${file.size}-${crypto.randomUUID()}`;
        const problem = precheckFile(file, limits);
        if (!problem) queue.push({ file, key });
        return { key, name: file.name, size: file.size, state: problem ? "error" : "uploading", progress: 0, error: problem ?? undefined };
      });
      setItems((prev) => [...added, ...prev].slice(0, 20));

      const worker = async () => {
        for (let next = queue.shift(); next; next = queue.shift()) {
          const { file, key } = next;
          try {
            const doc = await uploadDocument(file, { onProgress: (p) => update(key, { progress: p }) });
            update(key, { state: "done", progress: 100, documentId: doc.id });
            invalidate();
          } catch (error) {
            update(key, {
              state: "error",
              error: errorMessage(error),
              duplicateId: isApiError(error) ? error.details.document_id : undefined,
            });
          }
        }
      };
      await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    },
    [limits, update, invalidate],
  );

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) void start(Array.from(event.dataTransfer.files));
  }

  const accept = limits?.allowed_extensions.join(",") ?? ".pdf,.docx,.md,.txt,.png,.jpg,.jpeg";

  return (
    <div className="grid gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed bg-white px-6 py-8 text-center transition-colors",
          dragging ? "border-teal-500 bg-teal-50" : "border-input",
          disabled && "opacity-60",
        )}
      >
        <span className="grid size-12 place-items-center rounded-full bg-teal-50 text-teal-700">
          <UploadCloud className="size-6" aria-hidden />
        </span>
        <div className="grid gap-1">
          <p className="font-medium text-navy-900">Drag and drop files here</p>
          <p className="text-sm text-muted-foreground">
            PDF, Word, Markdown, text, or a scan or photo (PNG, JPEG). Up to {limits?.max_file_mb ?? "…"} MB each.
          </p>
        </div>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={accept}
          className="sr-only"
          disabled={disabled || !limits}
          onChange={(e) => {
            void start(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        <Button type="button" onClick={() => inputRef.current?.click()} disabled={disabled || !limits}>
          <FileUp aria-hidden /> Choose files
        </Button>
      </div>

      {items.length > 0 ? (
        <ul className="grid gap-2" aria-label="Uploads" aria-live="polite">
          {items.map((item) => (
            <li key={item.key} className="flex items-center gap-3 rounded-xl border bg-white px-3 py-2.5">
              {item.state === "uploading" ? (
                <Loader2 className="size-4 shrink-0 animate-spin text-navy-600" aria-label="Uploading" />
              ) : item.state === "done" ? (
                <CheckCircle2 className="size-4 shrink-0 text-teal-600" aria-label="Uploaded" />
              ) : (
                <XCircle className="size-4 shrink-0 text-destructive" aria-label="Failed" />
              )}
              <div className="grid min-w-0 flex-1 gap-1">
                <div className="flex items-baseline gap-2">
                  <span className="truncate text-sm font-medium text-navy-900">{item.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{formatBytes(item.size)}</span>
                </div>
                {item.state === "uploading" ? (
                  <Progress value={item.progress} className="h-1.5" aria-label={`Uploading ${item.name}`} />
                ) : item.state === "done" ? (
                  <p className="text-xs text-muted-foreground">Uploaded. Processing has started.</p>
                ) : (
                  <p className="text-xs text-destructive" role="alert">
                    {item.error}{" "}
                    {item.duplicateId ? (
                      <Link href={`/knowledge-base/${item.duplicateId}`} className="font-medium underline">
                        Open it
                      </Link>
                    ) : null}
                  </p>
                )}
              </div>
              {item.state !== "uploading" ? (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Dismiss ${item.name}`}
                  onClick={() => setItems((prev) => prev.filter((it) => it.key !== item.key))}
                >
                  <X aria-hidden />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
