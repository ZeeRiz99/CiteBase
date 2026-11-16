import { describe, expect, it } from "vitest";

import { escapeHtml, findPassage, normalize } from "@/lib/highlight";

const FI = String.fromCharCode(0xfb01); // the "fi" ligature pdf.js often returns
const SOFT_HYPHEN = String.fromCharCode(0xad);

// A page as pdf.js returns it: header, lines split into items, hyphenation, a ligature.
const ITEMS = [
  "Northwind Outfitters  DEMO DATA",
  "Returns policy",
  "Customers may return regular items within 30 days of de-",
  "livery. Sale items can be returned within 14 days. Re-",
  `funds go to the original payment method; ${FI}nal sale goods`,
  "are excluded.",
  "Page 3 of 12",
];

describe("normalize", () => {
  it("drops case, punctuation, whitespace, hyphens and ligatures", () => {
    expect(normalize(`De-livery, ${FI}nal  SALE!`)).toBe("deliveryfinalsale");
    expect(normalize(`re${SOFT_HYPHEN}turn`)).toBe("return");
    expect(normalize("Café 30 €")).toBe("cafe30");
  });
});

describe("findPassage", () => {
  it("finds an exact passage across hyphenated lines and ligatures", () => {
    const passage =
      "Customers may return regular items within 30 days of delivery. Sale items can be returned within 14 days.";
    const match = findPassage(ITEMS, passage);
    expect(match.matched).toBe(true);
    expect(match.coverage).toBe(1);
    expect([...match.items].sort()).toEqual([2, 3]);
  });

  it("tolerates small differences between extractors", () => {
    // Our extractor joined the hyphenation differently and kept a double space.
    const passage =
      "Refunds go to the original  payment method; final sale goods are excluded. Customers may return regular items";
    const match = findPassage(ITEMS, passage);
    expect(match.matched).toBe(true);
    expect(match.items.has(4)).toBe(true);
    expect(match.items.has(0)).toBe(false); // never the header
  });

  it("matches the part of a passage that continues on the next page", () => {
    const passage =
      "Sale items can be returned within 14 days. Refunds go to the original payment method; final sale goods are excluded. " +
      "Exchanges are free of charge for the first item and handled by the support team within two business days.";
    const match = findPassage(ITEMS, passage);
    expect(match.matched).toBe(true);
    expect(match.items.has(3) && match.items.has(5)).toBe(true);
  });

  it("reports no match for text that is not on the page", () => {
    const match = findPassage(ITEMS, "Annual leave accrues monthly from the start date for every new employee.");
    expect(match.matched).toBe(false);
    expect(match.items.size).toBe(0);
  });

  it("handles empty inputs", () => {
    expect(findPassage([], "anything").matched).toBe(false);
    expect(findPassage(ITEMS, "  ").matched).toBe(false);
  });
});

describe("escapeHtml", () => {
  it("escapes markup in text-layer strings", () => {
    expect(escapeHtml(`<img src=x onerror="a">&'`)).toBe("&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;");
  });
});
