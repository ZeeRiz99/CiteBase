"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileSearch, MessagesSquare, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Composer } from "@/components/chat/composer";
import { ConversationList } from "@/components/chat/conversation-list";
import { AssistantMessage, UserMessage, answerFromMessage, type AnswerView } from "@/components/chat/message-item";
import { SourceSheet } from "@/components/chat/source-viewer";
import { SourcesPanel } from "@/components/chat/sources-panel";
import { TraceSheet } from "@/components/chat/trace-sheet";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, isApiError } from "@/lib/api";
import { hasRole, useMe } from "@/lib/auth";
import {
  askPath,
  chatKeys,
  createConversation,
  regeneratePath,
  streamTurn,
  useFeedback,
  useSuggestedQuestions,
  useThread,
  type ChatMessage,
  type ConversationDetail,
  type Rating,
  type Source,
} from "@/lib/chat";
import { documentKeys, useDashboardSummary } from "@/lib/documents";
import { cn } from "@/lib/utils";

type LiveTurn = {
  token: number;
  conversationId: string;
  question: string | null; // null when regenerating
  replaces: string | null; // the answer being regenerated
  answer: AnswerView;
};

type Pane = "chats" | "chat" | "sources";

const EMPTY_ANSWER: AnswerView = {
  id: null,
  text: "",
  sources: [],
  evidence: null,
  phase: "searching",
  refusalReason: null,
  feedback: null,
  error: null,
};

export function conversationIdFrom(pathname: string): string | null {
  const match = /^\/chat\/([0-9a-f-]{36})\/?$/i.exec(pathname);
  return match ? match[1] : null;
}

export function ChatView() {
  const pathname = usePathname();
  const activeId = conversationIdFrom(pathname);
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const isAdmin = hasRole(me?.role, "admin");
  const canAsk = hasRole(me?.role, "viewer"); // every role may ask; uploads need member
  const summary = useDashboardSummary();
  const indexed = summary.data?.documents.indexed ?? 0;
  // Only a successful answer of "zero" means no documents; a failed request must not block asking.
  const noDocuments = summary.isSuccess && indexed === 0;
  const thread = useThread(activeId);
  const suggestions = useSuggestedQuestions(indexed > 0);
  const feedback = useFeedback(activeId);

  const [turn, setTurn] = useState<LiveTurn | null>(null);
  const [draft, setDraft] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [openSource, setOpenSource] = useState<Source | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [pane, setPane] = useState<Pane>("chat");
  const abortRef = useRef<AbortController | null>(null);
  const tokenRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const busy = turn !== null;
  const messages = useMemo(
    () => (thread.data?.messages ?? []).filter((m) => m.id !== turn?.replaces),
    [thread.data, turn?.replaces],
  );
  const showTurn = turn !== null && turn.conversationId === activeId;
  const answers = messages.filter((m) => m.role === "assistant");
  const latestAnswer = answers.at(-1) ?? null;

  const selectedSources = useMemo(() => {
    if (showTurn && (selectedId === null || selectedId === turn.answer.id) && turn.answer.sources.length) {
      return turn.answer.sources;
    }
    const target = messages.find((m) => m.id === selectedId) ?? latestAnswer;
    return target ? target.sources : null;
  }, [showTurn, selectedId, turn, messages, latestAnswer]);

  // Keep the newest text in view while an answer streams.
  const liveText = showTurn ? turn.answer.text : "";
  useEffect(() => {
    const box = scrollRef.current;
    if (box) box.scrollTo({ top: box.scrollHeight });
  }, [liveText, messages.length, showTurn]);

  const navigate = useCallback((id: string | null) => {
    window.history.pushState(null, "", id ? `/chat/${id}` : "/chat");
    setSelectedId(null);
    setPane("chat");
  }, []);

  const refreshAfterTurn = useCallback(
    async (conversationId: string) => {
      await queryClient.invalidateQueries({ queryKey: chatKeys.thread(conversationId) });
      void queryClient.invalidateQueries({ queryKey: chatKeys.allConversations });
      void queryClient.invalidateQueries({ queryKey: documentKeys.summary });
      void queryClient.invalidateQueries({ queryKey: chatKeys.allUnanswered });
      void queryClient.invalidateQueries({ queryKey: chatKeys.usage });
    },
    [queryClient],
  );

  const run = useCallback(
    async (path: string, body: unknown, conversationId: string, question: string | null, replaces: string | null) => {
      const token = ++tokenRef.current;
      const controller = new AbortController();
      abortRef.current = controller;
      setTurn({ token, conversationId, question, replaces, answer: EMPTY_ANSWER });
      setSelectedId(null);
      const update = (fn: (a: AnswerView) => AnswerView) =>
        setTurn((t) => (t && t.token === token ? { ...t, answer: fn(t.answer) } : t));
      let started = false;
      try {
        await streamTurn(
          path,
          body,
          {
            onMeta: (meta) => {
              started = true;
              update((a) => ({ ...a, id: meta.message_id, sources: meta.sources, evidence: meta.evidence, phase: "streaming" }));
            },
            onToken: (text) => update((a) => ({ ...a, text: a.text + text })),
            onReplace: (text) => update((a) => ({ ...a, text })),
            onRefusal: (r) => update((a) => ({ ...a, text: r.text, phase: "refused", refusalReason: r.reason })),
            onError: (e) => update((a) => ({ ...a, error: e.message })),
            onDone: (message: ChatMessage) => update(() => answerFromMessage(message)),
          },
          controller.signal,
        );
      } catch (error) {
        if (controller.signal.aborted) {
          update((a) => ({ ...a, phase: "stopped" }));
          await new Promise((r) => setTimeout(r, 500)); // let the server record the stopped answer
        } else if (!started) {
          // Rejected before streaming (limits, validation): nothing was saved; give the question back.
          setTurn((t) => (t && t.token === token ? null : t));
          if (question) setDraft(question);
          toast.error(errorMessage(error));
          if (isApiError(error) && error.code === "conflict") await refreshAfterTurn(conversationId);
          return;
        } else {
          update((a) => ({ ...a, phase: "error", error: "The connection was interrupted. Reload to see the saved answer." }));
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
      }
      await refreshAfterTurn(conversationId);
      setTurn((t) => (t && t.token === token ? null : t));
    },
    [refreshAfterTurn],
  );

  const ask = useCallback(
    async (question: string) => {
      if (busy) return;
      let conversationId = activeId;
      if (!conversationId) {
        try {
          const created = await createConversation();
          conversationId = created.id;
          queryClient.setQueryData<ConversationDetail>(chatKeys.thread(created.id), { ...created, messages: [] });
          window.history.pushState(null, "", `/chat/${created.id}`);
          void queryClient.invalidateQueries({ queryKey: chatKeys.allConversations });
        } catch (error) {
          setDraft(question);
          toast.error(errorMessage(error));
          return;
        }
      }
      await run(askPath(conversationId), { question }, conversationId, question, null);
    },
    [activeId, busy, queryClient, run],
  );

  const regenerate = useCallback(
    (message: ChatMessage) => {
      if (busy || !activeId) return;
      void run(regeneratePath(message.id), undefined, activeId, null, message.id);
    },
    [activeId, busy, run],
  );

  const rate = useCallback(
    (messageId: string, rating: Rating | null, comment?: string) =>
      feedback.mutate(
        { messageId, rating, comment },
        {
          onSuccess: () => {
            if (rating === "not_helpful") toast.success("Thanks. Your admins can review this answer.");
          },
          onError: (error) => toast.error(errorMessage(error)),
        },
      ),
    [feedback],
  );

  const showSources = (id: string | null) => {
    setSelectedId(id);
    setPane("sources");
  };

  const disabledReason = !canAsk
    ? "Viewers can read answers but not ask questions."
    : noDocuments
      ? "Upload a document to start asking questions."
      : undefined;
  const notFound = isApiError(thread.error) && thread.error.status === 404;
  const empty = messages.length === 0 && !showTurn;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex gap-1 border-b bg-white px-3 py-2 xl:hidden" role="tablist" aria-label="Chat panels">
        {(
          [
            ["chats", "Chats", MessagesSquare, "lg:hidden"],
            ["chat", "Answer", Sparkles, ""],
            ["sources", "Sources", FileSearch, ""],
          ] as const
        ).map(([key, label, Icon, extra]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={pane === key}
            onClick={() => setPane(key)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
              pane === key ? "bg-navy-50 text-navy-900" : "text-muted-foreground",
              extra,
            )}
          >
            <Icon className="size-4" aria-hidden /> {label}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1">
        <aside
          aria-label="Conversation history"
          className={cn(
            "min-h-0 flex-col border-r bg-white/70 p-3 lg:flex lg:w-72 lg:shrink-0",
            pane === "chats" ? "flex w-full" : "hidden",
          )}
        >
          <ConversationList activeId={activeId} onSelect={navigate} onNew={() => navigate(null)} />
        </aside>

        <section
          aria-label="Conversation"
          className={cn(
            "min-h-0 min-w-0 flex-1 flex-col",
            pane === "chat" ? "flex" : pane === "chats" ? "hidden lg:flex" : "hidden xl:flex",
          )}
        >
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto grid w-full max-w-3xl gap-4 px-4 py-6 sm:px-6">
              {activeId && thread.isPending ? (
                <div className="grid gap-4" aria-busy="true">
                  <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl" />
                  <Skeleton className="h-32 rounded-2xl" />
                </div>
              ) : notFound ? (
                <div className="grid justify-items-center gap-3 py-16 text-center">
                  <p className="font-medium text-navy-900">This conversation does not exist or was deleted.</p>
                  <Button onClick={() => navigate(null)}>Start a new conversation</Button>
                </div>
              ) : thread.isError ? (
                <p className="text-sm text-destructive" role="alert">
                  {errorMessage(thread.error)}
                </p>
              ) : empty ? (
                <EmptyState
                  noDocuments={noDocuments}
                  loading={summary.isPending}
                  canAsk={canAsk}
                  suggestions={suggestions.data?.questions ?? []}
                  suggestionsLoading={suggestions.isFetching}
                  onPick={(q) => void ask(q)}
                />
              ) : (
                <>
                  {messages.map((m) =>
                    m.role === "user" ? (
                      <UserMessage key={m.id} text={m.content} />
                    ) : (
                      <AssistantMessage
                        key={m.id}
                        answer={answerFromMessage(m)}
                        selected={selectedId === m.id}
                        actions={{
                          onOpenSource: setOpenSource,
                          onShowSources: () => showSources(m.id),
                          onRegenerate:
                            canAsk && !busy && m.id === latestAnswer?.id && m.status !== "streaming"
                              ? () => regenerate(m)
                              : undefined,
                          onFeedback: canAsk && m.status !== "streaming" ? (r, c) => rate(m.id, r, c) : undefined,
                          onTrace: isAdmin ? () => setTraceId(m.id) : undefined,
                        }}
                      />
                    ),
                  )}
                  {showTurn ? (
                    <>
                      {turn.question ? <UserMessage text={turn.question} /> : null}
                      <AssistantMessage
                        answer={turn.answer}
                        selected={false}
                        actions={{ onOpenSource: setOpenSource, onShowSources: () => showSources(turn.answer.id) }}
                      />
                    </>
                  ) : null}
                </>
              )}
            </div>
          </div>
          <div className="border-t bg-background/90 px-4 py-3 sm:px-6">
            <div className="mx-auto max-w-3xl">
              <Composer
                value={draft}
                onChange={setDraft}
                busy={busy}
                disabled={disabledReason !== undefined}
                disabledReason={disabledReason}
                onSend={(q) => void ask(q)}
                onStop={() => abortRef.current?.abort()}
              />
            </div>
          </div>
        </section>

        <aside
          aria-label="Sources"
          className={cn(
            "min-h-0 flex-col overflow-y-auto border-l bg-white/70 p-4 xl:flex xl:w-80 xl:shrink-0",
            pane === "sources" ? "flex w-full" : "hidden",
          )}
        >
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-navy-900">
            <BookOpen className="size-4 text-teal-700" aria-hidden /> Sources
          </h2>
          <SourcesPanel sources={selectedSources} onOpen={setOpenSource} />
        </aside>
      </div>

      <SourceSheet source={openSource} onClose={() => setOpenSource(null)} />
      {isAdmin ? <TraceSheet messageId={traceId} onClose={() => setTraceId(null)} /> : null}
    </div>
  );
}

function EmptyState({
  noDocuments,
  loading,
  canAsk,
  suggestions,
  suggestionsLoading,
  onPick,
}: {
  noDocuments: boolean;
  loading: boolean;
  canAsk: boolean;
  suggestions: string[];
  suggestionsLoading: boolean;
  onPick: (question: string) => void;
}) {
  if (loading) return <Skeleton className="h-40 rounded-2xl" />;
  if (noDocuments) {
    return (
      <div className="grid justify-items-center gap-3 py-16 text-center">
        <span className="grid size-12 place-items-center rounded-full bg-teal-50">
          <Upload className="size-6 text-teal-700" aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-navy-900">Add documents to ask about</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          Answers come only from your knowledge base. Upload a policy, handbook or guide and ask about it here.
        </p>
        <Button asChild>
          <Link href="/knowledge-base">Go to knowledge base</Link>
        </Button>
      </div>
    );
  }
  return (
    <div className="grid justify-items-center gap-5 py-12 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-teal-50">
        <Sparkles className="size-6 text-teal-700" aria-hidden />
      </span>
      <div className="grid gap-1">
        <h2 className="text-lg font-semibold text-navy-900">Ask your documents</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Every answer cites the passages it comes from. If your documents do not cover a question, you will be told so.
        </p>
      </div>
      {canAsk && (suggestions.length > 0 || suggestionsLoading) ? (
        <div className="grid w-full max-w-xl gap-2">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Try asking</p>
          {suggestionsLoading && suggestions.length === 0 ? (
            <>
              <Skeleton className="h-10 rounded-xl" />
              <Skeleton className="h-10 rounded-xl" />
            </>
          ) : (
            suggestions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onPick(q)}
                className="rounded-xl border bg-white px-4 py-2.5 text-left text-sm text-navy-900 shadow-soft transition-colors hover:border-teal-500/60"
              >
                {q}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
