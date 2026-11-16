import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Evidence } from "@/lib/chat";
import { cn } from "@/lib/utils";

const STYLE: Record<Evidence, { label: string; hint: string; className: string; Icon: typeof ShieldCheck }> = {
  strong: {
    label: "Strong evidence",
    hint: "A passage in your documents closely matches this question.",
    className: "border-teal-600/30 bg-teal-50 text-teal-700",
    Icon: ShieldCheck,
  },
  partial: {
    label: "Partial evidence",
    hint: "Related passages were found, but the match is not exact. Check the sources.",
    className: "border-warning/30 bg-amber-50 text-warning",
    Icon: ShieldQuestion,
  },
  weak: {
    label: "Weak evidence",
    hint: "Nothing in your documents matches this question closely enough to answer it.",
    className: "border-border bg-muted text-muted-foreground",
    Icon: ShieldAlert,
  },
};

/** Evidence comes from retrieval signals measured on the server, never from the model's opinion. */
export function EvidenceBadge({ evidence }: { evidence: Evidence }) {
  const { label, hint, className, Icon } = STYLE[evidence];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", className)}
        >
          <Icon className="size-3.5" aria-hidden />
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-60">{hint}</TooltipContent>
    </Tooltip>
  );
}
