import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeBaseView } from "@/components/documents/knowledge-base-view";
import { TooltipProvider } from "@/components/ui/tooltip";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const limits = { max_file_mb: 25, max_documents: 200, document_count: 0, allowed_extensions: [".docx", ".md", ".pdf", ".txt"] };

function version(status: string, extra: Record<string, unknown> = {}) {
  return {
    id: "v1",
    version_number: 1,
    original_filename: "Handbook.pdf",
    file_ext: ".pdf",
    size_bytes: 2048,
    page_count: 12,
    status,
    error_code: null,
    error_message: null,
    chunk_count: 30,
    is_current: true,
    created_at: "2026-11-14T10:00:00Z",
    indexed_at: null,
    ...extra,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}

function respond(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })));
}

afterEach(() => vi.unstubAllGlobals());

describe("KnowledgeBaseView", () => {
  it("shows the empty state when there are no documents", async () => {
    respond({ items: [], total: 0, page: 1, page_size: 25, limits });
    render(<KnowledgeBaseView />, { wrapper });
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeEnabled();
    expect(screen.getByText(/0 of 200 documents used/)).toBeInTheDocument();
  });

  it("lists documents with their status and error explanation", async () => {
    respond({
      items: [
        { id: "d1", title: "Handbook", collection_id: "c", created_at: "", updated_at: "", has_current_version: true, latest: version("indexed") },
        {
          id: "d2",
          title: "Scanned memo",
          collection_id: "c",
          created_at: "",
          updated_at: "",
          has_current_version: false,
          latest: version("needs_ocr", { error_message: "This PDF appears to be scanned." }),
        },
      ],
      total: 2,
      page: 1,
      page_size: 25,
      limits: { ...limits, document_count: 2 },
    });
    render(<KnowledgeBaseView />, { wrapper });
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByRole("link", { name: "Handbook" })).toHaveAttribute("href", "/knowledge-base/d1");
    expect(within(rows[1]).getByText("Ready")).toBeInTheDocument();
    expect(within(rows[2]).getByRole("button", { name: /needs_ocr: This PDF appears to be scanned/ })).toBeInTheDocument();
  });

  it("disables uploads at the workspace limit", async () => {
    respond({ items: [], total: 0, page: 1, page_size: 25, limits: { ...limits, document_count: 200 } });
    render(<KnowledgeBaseView />, { wrapper });
    expect(await screen.findByText(/reached your workspace limit/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose files" })).toBeDisabled();
  });
});
