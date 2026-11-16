"use client";

import {
  AlertTriangle,
  Copy,
  FileSearch,
  Info,
  Loader2,
  RotateCcw,
  SearchX,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AnswerMarkdown } from "@/components/chat/answer-markdown";
import { EvidenceBadge } from "@/components/chat/evidence-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ChatMessage, Evidence, MessageStatus, Rating, RefusalReason, Source } from "@/lib/chat";
import { cn } from "@/lib/utils";

export type AnswerPhase = MessageStatus | "searching" | "verifying";

export type AnswerView = {
  id: string | null;
  text: string;
  sources: Source[];
  evidence: Evidence | null;
  phase: AnswerPhase;
  refusalReason: RefusalReason | null;
  feedback: ChatMessage["feedback"];
  error: string | null;
};

export function answerFromMessage(message: ChatMessage): AnswerView {
  return {
    id: message.id,
    text: message.content,
    sources: message.sources,
    evidence: message.evidence,
    phase: message.status,
    refusalReason: message.refusal_reason,
    feedback: message.feedback,
    error: message.status === "error" ? "The AI service did not finish this answer." : null,
  };
}

export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-navy-900 px-4 py-2.5 text-[15px] leading-6 whitespace-pre-wrap text-white">
        {text}
      </p>
    </div>
  );
}

const REFUSAL_HINT: Record<RefusalReason, string> = {
  gate: "No passage in your documents is close enough to this question.",
  model: "The closest passages did not actually answer it.",
  no_valid_citation: "An answer was drafted but could not be tied to a passage, so it was withheld.",
};

type Actions = {
  onOpenSource: (source: Source) => void;
  onShowSources?: () => void;
  onRegenerate?: () => void;
  onFeedback?: (rating: Rating | null, comment?: string) => void;
  onTrace?: () => void;
};

export function AssistantMessage({
  answer,
  selected,
  actions,
}: {
  answer: AnswerView;
  selected: boolean;
  actions: Actions;
}) {
  const { phase } = answer;
  const live = phase === "searching" || phase === "streaming" || phase === "verifying";
  const cited = answer.sources.filter((s) => s.cited).length;

  return (
    <article
      aria-busy={live}
      className={cn(
        "grid gap-3 rounded-2xl border bg-white px-4 py-3.5 shadow-soft transition-colors sm:px-5",
        selected && "border-teal-500/50",
      )}
    >
      {answer.evidence || phase === "stopped" || phase === "verifying" ? (
        <div className="flex flex-wrap items-center gap-2">
          {answer.evidence ? <EvidenceBadge evidence={answer.evidence} /> : null}
          {phase === "verifying" ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground" role="status">
              <Loader2 className="size-3 animate-spin" aria-hidden /> Checking citations…
            </span>
          ) : null}
          {phase === "stopped" ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              <Square className="size-3" aria-hidden /> Stopped
            </span>
          ) : null}
        </div>
      ) : null}

      {phase === "searching" ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="size-4 animate-spin text-teal-700" aria-hidden /> Searching your documents…
        </p>
      ) : phase === "refused" ? (
        <div className="flex gap-3 rounded-xl bg-navy-50 p-3">
          <SearchX className="mt-0.5 size-5 shrink-0 text-navy-600" aria-hidden />
          <div className="grid gap-1">
            <p className="text-[15px] leading-6 font-medium text-navy-900">{answer.text}</p>
            {answer.refusalReason ? (
              <p className="text-sm text-muted-foreground">
                {REFUSAL_HINT[answer.refusalReason]} Try rephrasing, or{" "}
                <Link href="/knowledge-base" className="text-teal-700 underline underline-offset-2">
                  upload a document
                </Link>{" "}
                that covers it.
              </p>
            ) : null}
          </div>
        </div>
      ) : (
        <>
          {answer.text ? (
            <div className={cn(phase === "streaming" && "streaming-caret")}>
              <AnswerMarkdown text={answer.text} sources={answer.sources} onOpenSource={actions.onOpenSource} />
            </div>
          ) : phase === "stopped" ? (
            <p className="text-sm text-muted-foreground">Stopped before an answer was written.</p>
          ) : phase === "streaming" ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin text-teal-700" aria-hidden /> Writing an answer…
            </p>
          ) : null}
          {answer.error ? (
            <p className="flex items-center gap-2 text-sm text-destructive" role="alert">
              <AlertTriangle className="size-4 shrink-0" aria-hidden /> {answer.error}
            </p>
          ) : null}
        </>
      )}

      {!live && answer.id ? (
        <div className="-mx-1 flex flex-wrap items-center gap-0.5 border-t pt-2">
          {cited > 0 && actions.onShowSources ? (
            <Button variant="ghost" size="sm" onClick={actions.onShowSources} aria-pressed={selected}>
              <FileSearch aria-hidden /> {cited} {cited === 1 ? "source" : "sources"}
            </Button>
          ) : null}
          {phase !== "refused" && answer.text ? (
            <IconAction label="Copy answer" onClick={() => copyAnswer(answer)}>
              <Copy aria-hidden />
            </IconAction>
          ) : null}
          {actions.onRegenerate ? (
            <IconAction label="Regenerate answer" onClick={actions.onRegenerate}>
              <RotateCcw aria-hidden />
            </IconAction>
          ) : null}
          {actions.onFeedback ? <FeedbackButtons answer={answer} onFeedback={actions.onFeedback} /> : null}
          {actions.onTrace ? (
            <Button variant="ghost" size="sm" className="ml-auto text-muted-foreground" onClick={actions.onTrace}>
              <Info aria-hidden /> Why this answer?
            </Button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function IconAction({ label, onClick, pressed, children }: { label: string; onClick: () => void; pressed?: boolean; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          aria-pressed={pressed}
          onClick={onClick}
          className={cn("text-muted-foreground", pressed && "bg-teal-50 text-teal-700")}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function FeedbackButtons({ answer, onFeedback }: { answer: AnswerView; onFeedback: NonNullable<Actions["onFeedback"]> }) {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const rating = answer.feedback?.rating ?? null;
  return (
    <>
      <IconAction
        label={rating === "helpful" ? "Remove rating" : "Helpful"}
        pressed={rating === "helpful"}
        onClick={() => onFeedback(rating === "helpful" ? null : "helpful")}
      >
        <ThumbsUp aria-hidden />
      </IconAction>
      <IconAction
        label={rating === "not_helpful" ? "Remove rating" : "Not helpful"}
        pressed={rating === "not_helpful"}
        onClick={() => {
          if (rating === "not_helpful") onFeedback(null);
          else {
            setComment("");
            setOpen(true);
          }
        }}
      >
        <ThumbsDown aria-hidden />
      </IconAction>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>What was wrong with this answer?</DialogTitle>
            <DialogDescription>Optional. Your workspace admins see this to improve the documents.</DialogDescription>
          </DialogHeader>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
            rows={4}
            placeholder="For example: it cited the wrong policy, or missed the exception for sale items."
            aria-label="Comment"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                onFeedback("not_helpful", comment);
                setOpen(false);
              }}
            >
              Send feedback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function copyAnswer(answer: AnswerView) {
  const cited = answer.sources.filter((s) => s.cited);
  const list = cited.map((s) => `[${s.number}] ${s.document_title}, ${s.location}`).join("\n");
  const text = list ? `${answer.text}\n\nSources:\n${list}` : answer.text;
  navigator.clipboard.writeText(text).then(
    () => toast.success("Answer copied"),
    () => toast.error("Could not copy to the clipboard"),
  );
}
