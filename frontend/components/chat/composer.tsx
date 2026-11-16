"use client";

import { ArrowUp, Square } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const MAX_QUESTION = 2000; // mirrors the server's max_question_chars

export function Composer({
  busy,
  disabled,
  disabledReason,
  value,
  onChange,
  onSend,
  onStop,
}: {
  value: string;
  onChange: (value: string) => void;
  busy: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onSend: (question: string) => void;
  onStop: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const question = value.trim();
  const canSend = !busy && !disabled && question.length > 0 && question.length <= MAX_QUESTION;

  const send = () => {
    if (!canSend) return;
    onSend(question);
    onChange("");
    ref.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  };

  return (
    <form
      className="grid gap-1.5"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border bg-white p-2 shadow-raised focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/20",
          disabled && "opacity-70",
        )}
      >
        <label htmlFor="question" className="sr-only">
          Ask a question about your documents
        </label>
        <textarea
          id="question"
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          disabled={disabled}
          placeholder={disabled ? disabledReason : "Ask a question about your documents…"}
          className="field-sizing-content max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] leading-6 outline-none placeholder:text-muted-foreground focus-visible:outline-none"
        />
        {busy ? (
          <Button type="button" size="icon-lg" variant="secondary" onClick={onStop} aria-label="Stop generating">
            <Square className="fill-current" aria-hidden />
          </Button>
        ) : (
          <Button type="submit" size="icon-lg" disabled={!canSend} aria-label="Send question">
            <ArrowUp aria-hidden />
          </Button>
        )}
      </div>
      <p className="flex justify-between px-2 text-xs text-muted-foreground">
        <span>Answers come only from your documents, with sources. Enter to send, Shift+Enter for a new line.</span>
        {question.length > MAX_QUESTION - 200 ? (
          <span className={cn(question.length > MAX_QUESTION && "text-destructive")}>
            {question.length}/{MAX_QUESTION}
          </span>
        ) : null}
      </p>
    </form>
  );
}
