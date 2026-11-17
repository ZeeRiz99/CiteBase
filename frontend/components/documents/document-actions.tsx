"use client";

import { Download, FileUp, MoreHorizontal, RotateCw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { errorMessage } from "@/lib/api";
import { hasRole, useMe } from "@/lib/auth";
import {
  IN_PROGRESS,
  uploadDocument,
  useDeleteDocument,
  useInvalidateDocuments,
  useRetryDocument,
  type DocumentItem,
} from "@/lib/documents";

export function DocumentActions({
  document,
  afterDelete,
  variant = "menu",
}: {
  document: DocumentItem;
  afterDelete?: string;
  variant?: "menu" | "buttons";
}) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const retry = useRetryDocument();
  const remove = useDeleteDocument();
  const invalidate = useInvalidateDocuments();
  const { data: me } = useMe();
  // UI hints only; the API enforces the same rules (upload/retry: member, delete: admin).
  const canWrite = hasRole(me?.role, "member");
  const canDelete = hasRole(me?.role, "admin");
  const busy = IN_PROGRESS.has(document.latest.status);
  const canRetry = canWrite && document.latest.status === "failed";

  async function onNewVersion(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    try {
      await uploadDocument(file, { url: `/api/v1/documents/${document.id}/versions` });
      toast.success("New version uploaded", { description: "The current version stays live until it is processed." });
      invalidate();
    } catch (error) {
      toast.error("Upload failed", { description: errorMessage(error) });
    } finally {
      setUploading(false);
    }
  }

  function onRetry() {
    retry.mutate(document.id, {
      onSuccess: () => toast.success("Processing restarted"),
      onError: (error) => toast.error("Could not retry", { description: errorMessage(error) }),
    });
  }

  function onDelete() {
    remove.mutate(document.id, {
      onSuccess: (data) => {
        toast.success(`"${document.title}" deleted`, { description: data.message });
        setConfirmOpen(false);
        if (afterDelete) router.push(afterDelete);
      },
      onError: (error) => toast.error("Could not delete", { description: errorMessage(error) }),
    });
  }

  const fileUrl = `/api/v1/documents/${document.id}/file`;
  const accept = ".pdf,.docx,.md,.txt";

  return (
    <>
      <input
        ref={fileInput}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          void onNewVersion(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {variant === "buttons" ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <a href={fileUrl}>
              <Download aria-hidden /> Download
            </a>
          </Button>
          {canWrite ? (
            <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={busy || uploading}>
              <FileUp aria-hidden /> {uploading ? "Uploading…" : "Upload new version"}
            </Button>
          ) : null}
          {canRetry ? (
            <Button variant="outline" onClick={onRetry} disabled={retry.isPending}>
              <RotateCw aria-hidden /> Retry
            </Button>
          ) : null}
          {canDelete ? (
            <Button variant="destructive" onClick={() => setConfirmOpen(true)}>
              <Trash2 aria-hidden /> Delete
            </Button>
          ) : null}
        </div>
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${document.title}`}>
              <MoreHorizontal aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem asChild>
              <a href={fileUrl}>
                <Download aria-hidden /> Download original
              </a>
            </DropdownMenuItem>
            {canWrite ? (
              <DropdownMenuItem onSelect={() => fileInput.current?.click()} disabled={busy || uploading}>
                <FileUp aria-hidden /> Upload new version
              </DropdownMenuItem>
            ) : null}
            {canRetry ? (
              <DropdownMenuItem onSelect={onRetry} disabled={retry.isPending}>
                <RotateCw aria-hidden /> Retry processing
              </DropdownMenuItem>
            ) : null}
            {canDelete ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setConfirmOpen(true)}>
                  <Trash2 aria-hidden /> Delete
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{document.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              It disappears from your knowledge base and from answers immediately. The file and its index are
              permanently removed after the retention period.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                onDelete();
              }}
              disabled={remove.isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {remove.isPending ? "Deleting…" : "Delete document"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
