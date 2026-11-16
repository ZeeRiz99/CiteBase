/**
 * Find a cited passage in a PDF page's text layer.
 *
 * pdf.js text items never match our extracted text character for character (different spacing,
 * ligatures, hyphenation, headers we removed), so stored offsets cannot be applied directly.
 * Both sides are normalised to lowercase letters and digits only, then the passage is located
 * with fixed-size anchors (robust to small differences). The matched span is mapped back to the
 * text items it covers. A weak match returns `matched: false` and the viewer falls back to
 * outlining the page and showing the passage beside it.
 */

const ANCHOR = 24;
const MIN_COVERAGE = 0.35;

/** Lowercase, decompose ligatures and accents, keep letters and digits only. */
export function normalize(text: string): string {
  return text
    .normalize("NFKD") // ligatures and accents decompose; the filter below drops the marks
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

export type PassageMatch = { items: Set<number>; coverage: number; matched: boolean };

export function findPassage(items: readonly string[], passage: string): PassageMatch {
  // Normalised page text, and for every character the item it came from.
  let page = "";
  const owner: number[] = [];
  items.forEach((item, index) => {
    const norm = normalize(item);
    page += norm;
    for (let i = 0; i < norm.length; i += 1) owner.push(index);
  });
  const target = normalize(passage);
  const empty: PassageMatch = { items: new Set(), coverage: 0, matched: false };
  if (!page || !target) return empty;

  let start = -1;
  let end = -1;
  const exact = page.indexOf(target);
  let coverage = 0;
  if (exact !== -1) {
    start = exact;
    end = exact + target.length;
    coverage = 1;
  } else {
    // Anchors in passage order; each must be found after the previous one.
    const anchors = Math.max(1, Math.floor(target.length / ANCHOR));
    let found = 0;
    let cursor = 0;
    let targetStart = 0; // where in the passage the first / last matched anchor sit
    let targetEnd = 0;
    for (let a = 0; a < anchors; a += 1) {
      const piece = target.slice(a * ANCHOR, a * ANCHOR + ANCHOR);
      const at = page.indexOf(piece, cursor);
      if (at === -1) continue;
      // An anchor far beyond the last one is probably a repeated phrase elsewhere.
      if (start !== -1 && at - end > ANCHOR * 8) continue;
      if (start === -1) {
        start = at;
        targetStart = a * ANCHOR;
      }
      end = at + piece.length;
      targetEnd = a * ANCHOR + piece.length;
      cursor = end;
      found += 1;
    }
    // Anchors are fixed windows; grow the span over any agreeing text around them (e.g. the
    // passage's last words on this page, before it continues on the next one).
    if (start !== -1) {
      while (end < page.length && targetEnd < target.length && page[end] === target[targetEnd]) {
        end += 1;
        targetEnd += 1;
      }
      while (start > 0 && targetStart > 0 && page[start - 1] === target[targetStart - 1]) {
        start -= 1;
        targetStart -= 1;
      }
    }
    // The passage may continue on the next page: judge coverage on what this page can hold.
    const possible = Math.max(1, Math.min(anchors, Math.floor((page.length - (start === -1 ? 0 : start)) / ANCHOR)));
    coverage = found / possible;
    if (found < 2 && anchors >= 2) coverage = Math.min(coverage, 0.2);
  }
  if (start === -1 || coverage < MIN_COVERAGE) return { ...empty, coverage };

  const covered = new Set<number>();
  for (let i = start; i < end; i += 1) covered.add(owner[i]);
  return { items: covered, coverage, matched: true };
}

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape text-layer strings before they are returned as HTML from customTextRenderer. */
export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ESCAPES[c]);
}
