import { describe, expect, it } from "vitest";

import { SseParser, linkCitations, sourceLocation } from "@/lib/chat";

describe("SseParser", () => {
  it("parses events split across network chunks", () => {
    const parser = new SseParser();
    expect(parser.push('event: meta\ndata: {"evidence":"str')).toEqual([]);
    expect(parser.push('ong"}\n\nevent: token\ndata: {"text":"Hi "}\n\n: ping\n\nevent: tok')).toEqual([
      { event: "meta", data: { evidence: "strong" } },
      { event: "token", data: { text: "Hi " } },
    ]);
    expect(parser.push('en\ndata: {"text":"[1]"}\n\n')).toEqual([{ event: "token", data: { text: "[1]" } }]);
  });

  it("accepts CRLF line endings and skips malformed data", () => {
    const parser = new SseParser();
    expect(parser.push('event: done\r\ndata: {"message":{}}\r\n\r\nevent: token\ndata: {oops\n\n')).toEqual([
      { event: "done", data: { message: {} } },
    ]);
  });
});

describe("linkCitations", () => {
  it("turns markers and groups into citation links", () => {
    expect(linkCitations("Twenty days [1]. Carry over [1, 3].", null)).toBe(
      "Twenty days [1](#cite-1). Carry over [1](#cite-1)[3](#cite-3).",
    );
  });

  it("drops numbers that do not map to a source", () => {
    expect(linkCitations("Unlimited refunds [99]. Thirty days [2].", new Set([1, 2]))).toBe(
      "Unlimited refunds . Thirty days [2](#cite-2).",
    );
  });

  it("leaves code spans and ordinary brackets alone", () => {
    expect(linkCitations("Use `arr[1]` or [see below] [2]", new Set([2]))).toBe(
      "Use `arr[1]` or [see below] [2](#cite-2)",
    );
  });
});

describe("sourceLocation", () => {
  it("adds the section only when it is not already in the location", () => {
    expect(sourceLocation({ location: "Page 3", section_title: "Refunds" })).toBe("Page 3 · Refunds");
    expect(sourceLocation({ location: "Returns policy", section_title: "Returns policy" })).toBe("Returns policy");
    expect(sourceLocation({ location: "Returns policy › Time limits", section_title: "Time limits" })).toBe(
      "Returns policy › Time limits",
    );
    expect(sourceLocation({ location: "Page 1", section_title: null })).toBe("Page 1");
  });

  it("drops a leading heading that only repeats the document title", () => {
    const doc = { document_title: "Employee Handbook" };
    const leave = "Employee Handbook › Leave";
    expect(sourceLocation({ ...doc, location: "Employee Handbook", section_title: "Employee Handbook" })).toBe("");
    expect(sourceLocation({ ...doc, location: leave, section_title: leave })).toBe("Leave");
    expect(sourceLocation({ ...doc, location: "Page 2", section_title: leave })).toBe("Page 2 · Leave");
    expect(sourceLocation({ ...doc, location: "Leave policy", section_title: "Leave policy" })).toBe("Leave policy");
  });
});
