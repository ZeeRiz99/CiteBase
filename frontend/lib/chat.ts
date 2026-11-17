"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, getCsrfToken, parseApiError, refreshSession } from "@/lib/api";
import { documentKeys } from "@/lib/documents";

export type Evidence = "strong" | "partial" | "weak";
export type MessageStatus = "streaming" | "complete" | "stopped" | "refused" | "error";
export type RefusalReason = "gate" | "model" | "no_valid_citation";
export type Rating = "helpful" | "not_helpful";

export type Source = {
  number: number;
  chunk_id: string | null;
  document_id: string | null;
  document_title: string;
  section_title: string | null;
  location: string;
  page_start: number;
  page_end: number;
  snippet: string;
  cited: boolean;
  available: boolean;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  refusal_reason: RefusalReason | null;
  evidence: Evidence | null;
  created_at: string;
  regenerated_from_id: string | null;
  sources: Source[];
  feedback: { rating: Rating; comment: string | null } | null;
};

export type Conversation = { id: string; title: string; created_at: string; updated_at: string };
export type ConversationDetail = Conversation & { messages: ChatMessage[] };

export type Trace = {
  message_id: string;
  question: string | null;
  standalone_query: string | null;
  status: MessageStatus;
  evidence: Evidence | null;
  refusal_reason: RefusalReason | null;
  prompt_version: string | null;
  llm_provider: string | null;
  llm_model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  trace: {
    signals?: Record<string, number>;
    thresholds?: { vec_hi: number; vec_lo: number; kw_coverage: number };
    embedding_profile?: string;
    sources?: {
      number: number;
      document_title: string;
      location: string;
      vector_score: number | null;
      keyword_score: number | null;
      fused_score: number;
      cited: boolean;
    }[];
    timings_ms?: Record<string, number>;
    regenerated?: boolean;
    invalid_citations?: number[];
    stopped?: boolean;
  };
};

export type UnansweredItem = {
  id: string;
  question: string;
  reason: RefusalReason;
  status: "open" | "resolved" | "dismissed";
  message_id: string;
  created_at: string;
};

export type UnansweredList = { items: UnansweredItem[]; total: number; page: number; page_size: number };

export type Usage = { period_start: string; tokens_used: number; token_limit: number | null; cost_usd: number | null };

export type ChunkContext = {
  chunk: {
    id: string;
    chunk_index: number;
    page_start: number;
    page_end: number;
    section_title: string | null;
    char_start: number;
    char_end: number;
    text: string;
  };
  document: {
    id: string;
    title: string;
    version_id: string;
    version_number: number;
    is_current: boolean;
    file_ext: string;
    mime_type: string;
    page_count: number | null;
    ocr_pages: number;
  };
  previous: ChunkContext["chunk"] | null;
  next: ChunkContext["chunk"] | null;
  pages: { page_number: number; heading_path: string | null; text: string }[];
};

export const chatKeys = {
  conversations: (q: string) => ["conversations", q] as const,
  allConversations: ["conversations"] as const,
  thread: (id: string) => ["conversation", id] as const,
  trace: (id: string) => ["trace", id] as const,
  suggestions: ["suggested-questions"] as const,
  context: (chunkId: string) => ["chunk-context", chunkId] as const,
  unanswered: (status: string, page: number) => ["unanswered", status, page] as const,
  allUnanswered: ["unanswered"] as const,
  usage: ["usage"] as const,
};

export const REFUSAL_REASON_LABEL: Record<RefusalReason, string> = {
  gate: "No relevant passage found",
  model: "Sources did not answer it",
  no_valid_citation: "Answer could not be verified",
};

export function useConversations(q: string) {
  return useQuery({
    queryKey: chatKeys.conversations(q),
    queryFn: () => api.get<Conversation[]>(`/api/v1/conversations${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    placeholderData: keepPreviousData,
  });
}

export function useThread(id: string | null) {
  return useQuery({
    queryKey: chatKeys.thread(id ?? "none"),
    queryFn: () => api.get<ConversationDetail>(`/api/v1/conversations/${id}`),
    enabled: id !== null,
  });
}

export function useSuggestedQuestions(enabled: boolean) {
  return useQuery({
    queryKey: chatKeys.suggestions,
    queryFn: () => api.get<{ questions: string[] }>("/api/v1/suggested-questions"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useTrace(messageId: string | null) {
  return useQuery({
    queryKey: chatKeys.trace(messageId ?? "none"),
    queryFn: () => api.get<Trace>(`/api/v1/messages/${messageId}/trace`),
    enabled: messageId !== null,
  });
}

export function useChunkContext(chunkId: string | null) {
  return useQuery({
    queryKey: chatKeys.context(chunkId ?? "none"),
    queryFn: () => api.get<ChunkContext>(`/api/v1/chunks/${chunkId}/context`),
    enabled: chunkId !== null,
    retry: false,
  });
}

export function useUnanswered(status: string, page: number) {
  const search = new URLSearchParams({ page: String(page), page_size: "25" });
  if (status !== "all") search.set("status", status);
  return useQuery({
    queryKey: chatKeys.unanswered(status, page),
    queryFn: () => api.get<UnansweredList>(`/api/v1/unanswered-questions?${search}`),
    placeholderData: keepPreviousData,
  });
}

export function useUsage(enabled: boolean) {
  return useQuery({ queryKey: chatKeys.usage, queryFn: () => api.get<Usage>("/api/v1/workspace/usage"), enabled });
}

export function useUpdateUnanswered() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: UnansweredItem["status"] }) =>
      api.patch<UnansweredItem>(`/api/v1/unanswered-questions/${id}`, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: chatKeys.allUnanswered });
      void queryClient.invalidateQueries({ queryKey: documentKeys.summary });
    },
  });
}

export function useRenameConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch<Conversation>(`/api/v1/conversations/${id}`, { title }),
    onSuccess: (conversation) => {
      void queryClient.invalidateQueries({ queryKey: chatKeys.allConversations });
      void queryClient.invalidateQueries({ queryKey: chatKeys.thread(conversation.id) });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ message: string }>(`/api/v1/conversations/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: chatKeys.allConversations }),
  });
}

export function useFeedback(conversationId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, rating, comment }: { messageId: string; rating: Rating | null; comment?: string }) =>
      rating === null
        ? api.delete<{ message: string }>(`/api/v1/messages/${messageId}/feedback`)
        : api.post<{ message: string }>(`/api/v1/messages/${messageId}/feedback`, { rating, comment }),
    onSuccess: () => {
      if (conversationId) void queryClient.invalidateQueries({ queryKey: chatKeys.thread(conversationId) });
      void queryClient.invalidateQueries({ queryKey: documentKeys.summary });
    },
  });
}

// ---- Streaming -------------------------------------------------------------------------

export type MetaEvent = { conversation_id: string; message_id: string; evidence: Evidence; sources: Source[] };

export type StreamHandlers = {
  onMeta?: (meta: MetaEvent) => void;
  onToken?: (text: string) => void;
  onReplace?: (text: string) => void;
  onCitations?: (data: { evidence: Evidence; citations: Source[] }) => void;
  onRefusal?: (data: { text: string; reason: RefusalReason }) => void;
  onError?: (data: { code: string; message: string }) => void;
  onDone?: (message: ChatMessage) => void;
};

export type SseEvent = { event: string; data: unknown };

/** Incremental SSE parser: feed text chunks, get complete events. Handles events split across chunks. */
export class SseParser {
  private buffer = "";

  push(chunk: string): SseEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const events: SseEvent[] = [];
    let end = this.buffer.indexOf("\n\n");
    while (end !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) continue; // keep-alive comment
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length) {
        try {
          events.push({ event, data: JSON.parse(data.join("\n")) });
        } catch {
          // A malformed event is skipped; the final `done` carries the saved message anyway.
        }
      }
      end = this.buffer.indexOf("\n\n");
    }
    return events;
  }
}

function dispatch(handlers: StreamHandlers, { event, data }: SseEvent) {
  const d = data as Record<string, unknown>;
  switch (event) {
    case "meta":
      handlers.onMeta?.(data as MetaEvent);
      break;
    case "token":
      handlers.onToken?.(String(d.text ?? ""));
      break;
    case "replace":
      handlers.onReplace?.(String(d.text ?? ""));
      break;
    case "citations":
      handlers.onCitations?.(data as { evidence: Evidence; citations: Source[] });
      break;
    case "refusal":
      handlers.onRefusal?.(data as { text: string; reason: RefusalReason });
      break;
    case "error":
      handlers.onError?.(data as { code: string; message: string });
      break;
    case "done":
      handlers.onDone?.(d.message as ChatMessage);
      break;
  }
}

async function openStream(path: string, body: unknown, signal: AbortSignal): Promise<Response> {
  const send = async () =>
    fetch(path, {
      method: "POST",
      credentials: "same-origin",
      signal,
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "X-CSRF-Token": await getCsrfToken(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  let res = await send();
  if (res.status === 401 && (await refreshSession())) res = await send();
  if (!res.ok) throw parseApiError(res.status, await res.text().catch(() => ""));
  if (!res.body) throw new ApiError(0, "network_error", "The answer stream could not be opened.");
  return res;
}

/**
 * POST a turn and dispatch its Server-Sent Events. Errors before streaming (limits, validation)
 * reject with ApiError. Aborting the signal (Stop) closes the connection; the server saves the
 * partial answer as "stopped".
 */
export async function streamTurn(path: string, body: unknown, handlers: StreamHandlers, signal: AbortSignal) {
  const res = await openStream(path, body, signal);
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SseParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const event of parser.push(value)) dispatch(handlers, event);
  }
}

export function askPath(conversationId: string) {
  return `/api/v1/conversations/${conversationId}/messages`;
}

export function regeneratePath(messageId: string) {
  return `/api/v1/messages/${messageId}/regenerate`;
}

export async function createConversation(): Promise<Conversation> {
  return api.post<Conversation>("/api/v1/conversations", {});
}

// ---- Citation markers ------------------------------------------------------------------

const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

/**
 * Turn `[n]` / `[1, 3]` markers into Markdown links (`#cite-n`) the renderer shows as chips.
 * Numbers that are not among `valid` are dropped (the server strips them too; this covers the
 * stream before validation). Markers inside code spans are left alone.
 */
export function linkCitations(text: string, valid: ReadonlySet<number> | null): string {
  return text
    .split(/(`[^`]*`)/)
    .map((part, i) =>
      i % 2 === 1
        ? part
        : part.replace(MARKER, (_m, group: string) => {
            const nums = group
              .split(",")
              .map((n) => Number(n.trim()))
              .filter((n) => valid === null || valid.has(n));
            return nums.map((n) => `[${n}](#cite-${n})`).join("");
          }),
    )
    .join("");
}

const SEPARATOR = " › ";

/**
 * "Page 3 · Returns › Time limits", without repeating a section that is already the location, and
 * without a leading heading that only repeats the document title ("Handbook › Leave" in "Handbook").
 */
export function sourceLocation(
  source: Pick<Source, "location" | "section_title"> & Partial<Pick<Source, "document_title">>,
): string {
  const title = source.document_title?.trim().toLowerCase();
  const stripTitle = (value: string) => {
    if (!title) return value;
    const parts = value.split(SEPARATOR);
    return parts[0]?.trim().toLowerCase() === title ? parts.slice(1).join(SEPARATOR) : value;
  };
  const location = stripTitle(source.location); // "" when it only repeated the title
  const section = source.section_title ? stripTitle(source.section_title) : "";
  return section && section !== location && !location.includes(section) ? `${location} · ${section}` : location;
}
