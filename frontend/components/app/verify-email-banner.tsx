"use client";

import { useMutation } from "@tanstack/react-query";
import { MailWarning } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

export function useResendVerification() {
  return useMutation({
    mutationFn: () => api.post("/api/v1/auth/resend-verification"),
    onSuccess: () => toast.success("Confirmation email sent", { description: "Check your inbox for a new link." }),
    onError: (error) => toast.error("Could not send the email", { description: errorMessage(error) }),
  });
}

export function VerifyEmailBanner({ email }: { email: string }) {
  const resend = useResendVerification();
  return (
    <div className="border-b border-amber-200 bg-amber-50" role="status">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 text-sm sm:px-6 lg:px-10">
        <MailWarning className="size-4 shrink-0 text-warning" aria-hidden />
        <p className="text-amber-950">
          Confirm your email address. We sent a link to <span className="font-medium">{email}</span>.
        </p>
        <Button
          size="sm"
          variant="outline"
          className="border-amber-300 bg-white sm:ml-auto"
          onClick={() => resend.mutate()}
          disabled={resend.isPending}
        >
          {resend.isPending ? "Sending…" : "Resend email"}
        </Button>
      </div>
    </div>
  );
}
