"use client";

import { MessageSquare, MoreHorizontal, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { useConversations, useDeleteConversation, useRenameConversation, type Conversation } from "@/lib/chat";
import { cn } from "@/lib/utils";

export function ConversationList({
  activeId,
  onSelect,
  onNew,
}: {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const [q, setQ] = useState("");
  const conversations = useConversations(q.trim());
  const rename = useRenameConversation();
  const remove = useDeleteConversation();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [deleting, setDeleting] = useState<Conversation | null>(null);

  const saveRename = (id: string) => {
    const title = draft.trim();
    setEditing(null);
    if (!title) return;
    rename.mutate({ id, title }, { onError: (e) => toast.error(errorMessage(e)) });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <Button onClick={onNew} className="w-full justify-start">
        <Plus aria-hidden /> New conversation
      </Button>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search conversations"
          aria-label="Search conversations"
          className="pl-8"
          maxLength={200}
        />
      </div>
      <nav aria-label="Conversations" className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
        {conversations.isPending ? (
          <div className="grid gap-2">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        ) : conversations.isError ? (
          <p className="px-2 text-sm text-destructive">{errorMessage(conversations.error)}</p>
        ) : conversations.data.length === 0 ? (
          <p className="px-2 py-4 text-sm text-muted-foreground">
            {q ? "No conversations match." : "Your conversations will appear here."}
          </p>
        ) : (
          <ul className="grid gap-0.5">
            {conversations.data.map((c) => (
              <li key={c.id} className="group relative">
                {editing === c.id ? (
                  <Input
                    autoFocus
                    value={draft}
                    maxLength={200}
                    aria-label="Conversation title"
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => saveRename(c.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveRename(c.id);
                      if (e.key === "Escape") setEditing(null);
                    }}
                  />
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => onSelect(c.id)}
                      aria-current={c.id === activeId ? "page" : undefined}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-lg py-2 pr-9 pl-2.5 text-left text-sm transition-colors",
                        c.id === activeId ? "bg-navy-50 font-medium text-navy-900" : "text-slate-body hover:bg-muted",
                      )}
                    >
                      <MessageSquare className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                      <span className="truncate">{c.title}</span>
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          aria-label={`Actions for ${c.title}`}
                          className="absolute top-1/2 right-1.5 -translate-y-1/2 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 aria-expanded:opacity-100"
                        >
                          <MoreHorizontal aria-hidden />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() => {
                            setDraft(c.title);
                            setEditing(c.id);
                          }}
                        >
                          <Pencil aria-hidden /> Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(c)}>
                          <Trash2 aria-hidden /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </nav>

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{deleting?.title}&rdquo; will be removed from your list. Your documents are not affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const target = deleting;
                if (!target) return;
                remove.mutate(target.id, {
                  onSuccess: () => {
                    toast.success("Conversation deleted");
                    if (target.id === activeId) onNew();
                  },
                  onError: (e) => toast.error(errorMessage(e)),
                });
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
