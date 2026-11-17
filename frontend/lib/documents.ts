"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, getCsrfToken, isApiError, parseApiError, refreshSession } from "@/lib/api";

export type DocumentStatus =
  | "queued"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexed"
  | "failed"
  | "needs_ocr";

export const IN_PROGRESS: ReadonlySet<DocumentStatus> = new Set(["queued", "extracting", "chunking", "embedding"]);

export type Version = {
  id: string;
  version_number: number;
  original_filename: string;
  file_ext: string;
  size_bytes: number;
  page_count: number | null;
  status: DocumentStatus;
  error_code: string | null;
  error_message: string | null;
  chunk_count: number;
  ocr_pages: number; // pages read by text recognition (scans, images)
  ocr_confidence: number | null; // mean word confidence, 0-100
  is_current: boolean;
  created_at: string;
  indexed_at: string | null;
};

/** Below this mean confidence, recognized text may contain misread words. */
export const LOW_OCR_CONFIDENCE = 70;

export type DocumentItem = {
  id: string;
  title: string;
  collection_id: string;
  created_at: string;
  updated_at: string;
  has_current_version: boolean;
  latest: Version;
};

export type DocumentDetail = DocumentItem & { versions: Version[] };

export type Limits = {
  max_file_mb: number;
  max_documents: number;
  document_count: number;
  allowed_extensions: string[];
};

export type DocumentList = { items: DocumentItem[]; total: number; page: number; page_size: number; limits: Limits };

export type Chunk = {
  id: string;
  chunk_index: number;
  page_start: number;
  page_end: number;
  section_title: string | null;
  char_start: number;
  char_end: number;
  token_count: number;
  text: string;
};

export type ChunkList = { items: Chunk[]; total: number; page: number; page_size: number; version_id: string | null };

export type StatusFilter = "all" | "processing" | "indexed" | "attention";

export type DashboardSummary = {
  documents: { total: number; processing: number; indexed: number; attention: number };
  questions: { last_7d: number; last_30d: number; unanswered_open: number; helpful_rate: number | null; rated: number };
};

export const documentKeys = {
  all: ["documents"] as const,
  list: (params: { q: string; status: StatusFilter; page: number }) => ["documents", "list", params] as const,
  detail: (id: string) => ["documents", "detail", id] as const,
  chunks: (id: string, page: number) => ["documents", "chunks", id, page] as const,
  summary: ["dashboard", "summary"] as const,
};

const POLL_MS = 2000;

export function useDocuments(params: { q: string; status: StatusFilter; page: number }) {
  const search = new URLSearchParams({ page: String(params.page), page_size: "25" });
  if (params.q) search.set("q", params.q);
  if (params.status !== "all") search.set("status", params.status);
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => api.get<DocumentList>(`/api/v1/documents?${search}`),
    placeholderData: keepPreviousData,
    // Poll only while something is still processing.
    refetchInterval: (query) =>
      query.state.data?.items.some((d) => IN_PROGRESS.has(d.latest.status)) ? POLL_MS : false,
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: documentKeys.detail(id),
    queryFn: () => api.get<DocumentDetail>(`/api/v1/documents/${id}`),
    refetchInterval: (query) => (query.state.data && IN_PROGRESS.has(query.state.data.latest.status) ? POLL_MS : false),
  });
}

export function useChunks(id: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: documentKeys.chunks(id, page),
    queryFn: () => api.get<ChunkList>(`/api/v1/documents/${id}/chunks?page=${page}&page_size=10`),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: documentKeys.summary,
    queryFn: () => api.get<DashboardSummary>("/api/v1/dashboard/summary"),
    refetchInterval: (query) => ((query.state.data?.documents.processing ?? 0) > 0 ? POLL_MS : false),
  });
}

function useInvalidateDocuments() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    void queryClient.invalidateQueries({ queryKey: documentKeys.summary });
  };
}

export function useRetryDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (id: string) => api.post<DocumentItem>(`/api/v1/documents/${id}/retry`),
    onSuccess: invalidate,
  });
}

export function useDeleteDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ message: string }>(`/api/v1/documents/${id}`),
    onSuccess: invalidate,
  });
}

export { useInvalidateDocuments };

/** Client-side pre-check; the server validates again (type by content, not name). */
export function precheckFile(file: File, limits: Pick<Limits, "max_file_mb" | "allowed_extensions">): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!limits.allowed_extensions.includes(ext)) {
    return `Unsupported file type. Allowed: ${limits.allowed_extensions.join(", ")}.`;
  }
  if (file.size === 0) return "This file is empty.";
  if (file.size > limits.max_file_mb * 1024 * 1024) return `Larger than the ${limits.max_file_mb} MB limit.`;
  return null;
}

type UploadOptions = { url?: string; onProgress?: (percent: number) => void };

function xhrUpload(file: File, url: string, csrf: string, onProgress?: (p: number) => void): Promise<DocumentItem> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRF-Token", csrf);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText) as DocumentItem);
      else reject(parseApiError(xhr.status, xhr.responseText));
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", "Upload failed. Check your connection and try again."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Upload with progress (XHR), CSRF header, and one session refresh on 401. */
export async function uploadDocument(file: File, { url = "/api/v1/documents", onProgress }: UploadOptions = {}) {
  try {
    return await xhrUpload(file, url, await getCsrfToken(), onProgress);
  } catch (error) {
    if (isApiError(error) && error.status === 401 && (await refreshSession())) {
      return xhrUpload(file, url, await getCsrfToken(), onProgress);
    }
    throw error;
  }
}
