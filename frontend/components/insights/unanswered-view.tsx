"use client";

import { CheckCircle2, Info, MessageCircleQuestion, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { TraceSheet } from "@/components/chat/trace-sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { hasRole, useMe } from "@/lib/auth";
import { REFUSAL_REASON_LABEL, useUnanswered, useUpdateUnanswered, type UnansweredItem } from "@/lib/chat";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const FILTERS = [
  { key: "open", label: "Open" },
  { key: "resolved", label: "Resolved" },
  { key: "dismissed", label: "Dismissed" },
  { key: "all", label: "All" },
] as const;

type Filter = (typeof FILTERS)[number]["key"];

/** Questions the knowledge base could not answer: the to-do list for document owners. */
export function UnansweredView() {
  const { data: me } = useMe();
  const [filter, setFilter] = useState<Filter>("open");
  const [page, setPage] = useState(1);
  const [traceId, setTraceId] = useState<string | null>(null);
  const list = useUnanswered(filter, page);
  const update = useUpdateUnanswered();

  if (me && !hasRole(me.role, "admin")) {
    return <p className="text-muted-foreground">Only workspace admins can review unanswered questions.</p>;
  }

  const setStatus = (item: UnansweredItem, status: UnansweredItem["status"]) =>
    update.mutate(
      { id: item.id, status },
      { onError: (error) => toast.error(errorMessage(error)), onSuccess: () => toast.success("Updated") },
    );

  const data = list.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">Unanswered questions</h1>
        <p className="max-w-2xl text-muted-foreground">
          Questions your documents could not answer. Each one points at a gap: add or update a document that covers
          it, then mark it resolved.
        </p>
      </div>

      <div className="flex flex-wrap gap-1" role="tablist" aria-label="Filter by status">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            onClick={() => {
              setFilter(key);
              setPage(1);
            }}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium",
              filter === key ? "bg-navy-900 text-white" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <Card className="py-0 shadow-soft">
        <CardContent className="px-0">
          {list.isPending ? (
            <div className="grid gap-2 p-4">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          ) : list.isError ? (
            <p className="p-4 text-sm text-destructive">{errorMessage(list.error)}</p>
          ) : data && data.items.length === 0 ? (
            <div className="grid justify-items-center gap-2 px-4 py-14 text-center">
              <MessageCircleQuestion className="size-9 text-muted-foreground/60" aria-hidden />
              <p className="font-medium text-navy-900">{filter === "open" ? "Nothing waiting" : "Nothing here"}</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                When someone asks a question your documents do not cover, it is listed here instead of being guessed.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Question</TableHead>
                  <TableHead className="hidden md:table-cell">Why</TableHead>
                  <TableHead className="hidden sm:table-cell">Asked</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="pr-4 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-md pl-4 whitespace-normal">{item.question}</TableCell>
                    <TableCell className="hidden text-muted-foreground md:table-cell">
                      {REFUSAL_REASON_LABEL[item.reason]}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground sm:table-cell">
                      {formatDateTime(item.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.status === "open" ? "default" : "secondary"} className="capitalize">
                        {item.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="pr-4">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon-sm" aria-label="Why was it refused?" onClick={() => setTraceId(item.message_id)}>
                          <Info aria-hidden />
                        </Button>
                        {item.status === "open" ? (
                          <>
                            <Button variant="ghost" size="sm" onClick={() => setStatus(item, "resolved")}>
                              <CheckCircle2 aria-hidden /> Resolve
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setStatus(item, "dismissed")}>
                              <XCircle aria-hidden /> Dismiss
                            </Button>
                          </>
                        ) : (
                          <Button variant="ghost" size="sm" onClick={() => setStatus(item, "open")}>
                            <RotateCcw aria-hidden /> Reopen
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {pages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span className="text-muted-foreground">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </div>
      ) : null}

      <TraceSheet messageId={traceId} onClose={() => setTraceId(null)} />
    </div>
  );
}
