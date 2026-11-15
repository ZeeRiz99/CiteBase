import { describe, expect, it } from "vitest";

import { parseApiError } from "@/lib/api";
import { precheckFile } from "@/lib/documents";
import { fileTypeLabel, formatBytes } from "@/lib/format";

const limits = { max_file_mb: 1, allowed_extensions: [".docx", ".md", ".pdf", ".txt"] };

function file(name: string, size: number): File {
  return new File([new Uint8Array(size)], name);
}

describe("precheckFile", () => {
  it("accepts allowed types within the size limit, case-insensitively", () => {
    expect(precheckFile(file("Handbook.PDF", 10), limits)).toBeNull();
    expect(precheckFile(file("notes.md", 10), limits)).toBeNull();
  });

  it("rejects other types, empty files and oversized files", () => {
    expect(precheckFile(file("tool.exe", 10), limits)).toMatch(/Unsupported file type/);
    expect(precheckFile(file("noextension", 10), limits)).toMatch(/Unsupported file type/);
    expect(precheckFile(file("empty.txt", 0), limits)).toBe("This file is empty.");
    expect(precheckFile(file("big.pdf", 1024 * 1024 + 1), limits)).toBe("Larger than the 1 MB limit.");
  });
});

describe("parseApiError", () => {
  it("keeps structured details such as a duplicate document id", () => {
    const error = parseApiError(
      409,
      JSON.stringify({ error: { code: "duplicate_document", message: "Already uploaded.", details: { document_id: "d1" } } }),
    );
    expect(error.code).toBe("duplicate_document");
    expect(error.details.document_id).toBe("d1");
  });

  it("falls back to a generic message for non-JSON bodies", () => {
    const error = parseApiError(502, "<html>Bad gateway</html>");
    expect(error.status).toBe(502);
    expect(error.message).toMatch(/Something went wrong/);
  });
});

describe("format", () => {
  it.each([
    [512, "512 B"],
    [2048, "2.0 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
    [42 * 1024 * 1024, "42 MB"],
  ])("formatBytes(%i) = %s", (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });

  it("labels file types", () => {
    expect(fileTypeLabel(".docx")).toBe("Word");
    expect(fileTypeLabel(".pdf")).toBe("PDF");
  });
});
