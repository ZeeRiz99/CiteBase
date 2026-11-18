"use client";

import { MailWarning } from "lucide-react";

import { useResendVerification } from "@/components/app/verify-email-banner";
import { Button } from "@/components/ui/button";

/** Shown where an action waits for a confirmed email (uploads, invitations). */
export function ConfirmEmailNotice({ email, action }: { email: string; action: string }) {
  const resend = useResendVerification();
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm"
      role="status"
    >
      <MailWarning className="size-4 shrink-0 text-warning" aria-hidden />
      <p className="min-w-0 flex-1 text-amber-950">
        Confirm your email to {action}. Open the link we sent to <span className="font-medium">{email}</span>.
      </p>
      <Button
        size="sm"
        variant="outline"
        className="border-amber-300 bg-white"
        onClick={() => resend.mutate()}
        disabled={resend.isPending}
      >
        {resend.isPending ? "Sending…" : "Send a new link"}
      </Button>
    </div>
  );
}
