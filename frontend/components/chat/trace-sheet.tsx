"use client";

import { Check, X } from "lucide-react";
import type { ReactNode } from "react";

import { EvidenceBadge } from "@/components/chat/evidence-badge";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/api";
import { REFUSAL_REASON_LABEL, useTrace } from "@/lib/chat";

const fmt = (n: number | null | undefined, digits = 3) => (n === null || n === undefined ? "–" : n.toFixed(digits));

/** Admin "why this answer?": the gate's signals against its thresholds, every retrieved passage, cost. */
export function TraceSheet({ messageId, onClose }: { messageId: string | null; onClose: () => void }) {
  const query = useTrace(messageId);
  const t = query.data;
  const signals = t?.trace.signals ?? {};
  const thresholds = t?.trace.thresholds;

  return (
    <Sheet open={messageId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle>Why this answer?</SheetTitle>
          <SheetDescription>What retrieval found and how the relevance check decided. Visible to admins.</SheetDescription>
        </SheetHeader>
        <div className="grid gap-6 p-4 text-sm">
          {query.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : query.isError || !t ? (
            <p className="text-destructive">{errorMessage(query.error)}</p>
          ) : (
            <>
              <Section title="Question">
                <dl className="grid gap-2">
                  <Row label="Asked">{t.question ?? "–"}</Row>
                  {t.standalone_query && t.standalone_query !== t.question ? (
                    <Row label="Searched as">{t.standalone_query}</Row>
                  ) : null}
                  <Row label="Outcome">
                    <span className="flex flex-wrap items-center gap-2">
                      {t.evidence ? <EvidenceBadge evidence={t.evidence} /> : null}
                      <span className="capitalize">{t.status}</span>
                      {t.refusal_reason ? (
                        <span className="text-muted-foreground">({REFUSAL_REASON_LABEL[t.refusal_reason]})</span>
                      ) : null}
                    </span>
                  </Row>
                </dl>
              </Section>

              <Section title="Relevance check">
                <p className="mb-2 text-muted-foreground">
                  The model is only called when the best passage is similar enough to the question.
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Signal</TableHead>
                      <TableHead className="text-right">Value</TableHead>
                      <TableHead className="text-right">Threshold</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>Best vector similarity</TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(signals.vec_max)}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {thresholds ? `≥ ${fmt(thresholds.vec_hi, 2)} (or ≥ ${fmt(thresholds.vec_lo, 2)} with keywords)` : "–"}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Query terms found</TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(signals.kw_coverage, 2)}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {thresholds ? `≥ ${fmt(thresholds.kw_coverage, 2)}` : "–"}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Strong passages</TableCell>
                      <TableCell className="text-right tabular-nums">{signals.n_vec_strong ?? "–"}</TableCell>
                      <TableCell />
                    </TableRow>
                  </TableBody>
                </Table>
                {t.trace.embedding_profile ? (
                  <p className="mt-2 text-xs text-muted-foreground">Embedding profile: {t.trace.embedding_profile}</p>
                ) : null}
              </Section>

              <Section title="Retrieved passages">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>#</TableHead>
                      <TableHead>Document</TableHead>
                      <TableHead className="text-right">Vector</TableHead>
                      <TableHead className="text-right">Keyword</TableHead>
                      <TableHead className="text-right">Fused</TableHead>
                      <TableHead className="text-center">Cited</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(t.trace.sources ?? []).map((s) => (
                      <TableRow key={s.number}>
                        <TableCell className="tabular-nums">{s.number}</TableCell>
                        <TableCell className="max-w-48">
                          <span className="block truncate">{s.document_title}</span>
                          <span className="block text-xs text-muted-foreground">{s.location}</span>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(s.vector_score)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(s.keyword_score)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(s.fused_score, 4)}</TableCell>
                        <TableCell className="text-center">
                          {s.cited ? (
                            <Check className="mx-auto size-4 text-teal-700" aria-label="Cited" />
                          ) : (
                            <X className="mx-auto size-4 text-muted-foreground" aria-label="Not cited" />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Section>

              <Section title="Model and cost">
                <dl className="grid gap-2">
                  <Row label="Model">
                    {t.llm_provider ?? "–"} / {t.llm_model ?? "–"} · prompt {t.prompt_version ?? "–"}
                  </Row>
                  <Row label="Tokens">
                    {t.input_tokens ?? 0} in · {t.output_tokens ?? 0} out
                    {t.trace.stopped ? " (stopped: estimated)" : ""}
                  </Row>
                  <Row label="Cost">{t.cost_usd === null ? "Price not configured" : `USD ${t.cost_usd.toFixed(6)}`}</Row>
                  <Row label="Time">{t.latency_ms === null ? "–" : `${(t.latency_ms / 1000).toFixed(2)} s total`}</Row>
                  {t.trace.timings_ms ? (
                    <Row label="Stages">
                      {Object.entries(t.trace.timings_ms)
                        .filter(([key]) => key !== "total")
                        .map(([key, ms]) => `${key.replaceAll("_", " ")} ${Math.round(ms)} ms`)
                        .join(" · ")}
                    </Row>
                  ) : null}
                  {t.trace.regenerated ? <Row label="Note">Regenerated once to obtain valid citations.</Row> : null}
                </dl>
              </Section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-2">
      <h3 className="text-sm font-semibold text-navy-900">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}
