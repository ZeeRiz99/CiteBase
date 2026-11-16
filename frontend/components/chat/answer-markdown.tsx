"use client";

import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationChip } from "@/components/chat/citation-chip";
import { linkCitations, type Source } from "@/lib/chat";

const CITE = /^#cite-(\d+)$/;
// Remote images in an answer could leak that a user read it; raw HTML is never rendered.
const DISALLOWED = ["img"];

/**
 * Renders an answer as Markdown (no raw HTML) with [n] markers as citation chips. While the
 * answer streams, `valid` is null and every marker that maps to a sent source is shown; once the
 * server has validated it, only cited sources remain.
 */
export const AnswerMarkdown = memo(function AnswerMarkdown({
  text,
  sources,
  onOpenSource,
}: {
  text: string;
  sources: Source[];
  onOpenSource: (source: Source) => void;
}) {
  const byNumber = useMemo(() => new Map(sources.map((s) => [s.number, s])), [sources]);
  const valid = useMemo(() => new Set(byNumber.keys()), [byNumber]);
  const components = useMemo<Components>(
    () => ({
      a({ href, children }) {
        const cite = href ? CITE.exec(href) : null;
        if (cite) {
          const n = Number(cite[1]);
          return <CitationChip number={n} source={byNumber.get(n)} onOpen={onOpenSource} />;
        }
        const safe = href && /^https?:\/\//i.test(href) ? href : undefined;
        return safe ? (
          <a href={safe} target="_blank" rel="noopener noreferrer nofollow" className="text-teal-700 underline">
            {children}
          </a>
        ) : (
          <span>{children}</span>
        );
      },
    }),
    [byNumber, onOpenSource],
  );
  return (
    <div className="answer-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} disallowedElements={DISALLOWED} unwrapDisallowed>
        {linkCitations(text, valid)}
      </ReactMarkdown>
    </div>
  );
});
