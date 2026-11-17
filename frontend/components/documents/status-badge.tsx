import { AlertTriangle, CheckCircle2, Loader2, ScanText, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/documents";

const STATUS: Record<DocumentStatus, { label: string; className: string; icon: typeof Loader2; spin?: boolean }> = {
  queued: { label: "Queued", className: "bg-navy-50 text-navy-700 ring-navy-100", icon: Loader2, spin: true },
  extracting: { label: "Reading", className: "bg-navy-50 text-navy-700 ring-navy-100", icon: Loader2, spin: true },
  chunking: { label: "Indexing", className: "bg-navy-50 text-navy-700 ring-navy-100", icon: Loader2, spin: true },
  embedding: { label: "Embedding", className: "bg-navy-50 text-navy-700 ring-navy-100", icon: Loader2, spin: true },
  indexed: { label: "Ready", className: "bg-teal-50 text-teal-700 ring-teal-100", icon: CheckCircle2 },
  failed: { label: "Failed", className: "bg-red-50 text-destructive ring-red-100", icon: XCircle },
  needs_ocr: { label: "Needs OCR", className: "bg-amber-50 text-amber-800 ring-amber-200", icon: ScanText },
};

// "needs_ocr" covers three cases; the error code says which.
const OCR_LABELS: Record<string, string> = {
  ocr_no_text: "Unreadable scan",
  ocr_too_many_pages: "Scan too long",
};

export function StatusBadge({
  status,
  code,
  className,
}: {
  status: DocumentStatus;
  code?: string | null;
  className?: string;
}) {
  const base = STATUS[status] ?? { label: status, className: "bg-muted", icon: AlertTriangle };
  const s = status === "needs_ocr" && code && OCR_LABELS[code] ? { ...base, label: OCR_LABELS[code] } : base;
  const Icon = s.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        s.className,
        className,
      )}
    >
      <Icon className={cn("size-3.5", s.spin && "animate-spin")} aria-hidden />
      {s.label}
    </span>
  );
}

export function statusLabel(status: DocumentStatus, code?: string | null): string {
  if (status === "needs_ocr" && code && OCR_LABELS[code]) return OCR_LABELS[code];
  return STATUS[status]?.label ?? status;
}
