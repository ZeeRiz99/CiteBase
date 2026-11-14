"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { meQueryKey } from "@/lib/auth";

type State = { status: "verifying" } | { status: "done" } | { status: "error"; message: string };

export function VerifyEmail() {
  const token = useSearchParams().get("token");
  const queryClient = useQueryClient();
  const [state, setState] = useState<State>(
    token ? { status: "verifying" } : { status: "error", message: "This link is missing its token." },
  );
  // Tokens are single-use: guard against React running the effect twice in development.
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    api
      .post("/api/v1/auth/verify-email", { token })
      .then(() => {
        setState({ status: "done" });
        void queryClient.invalidateQueries({ queryKey: meQueryKey });
      })
      .catch((error: unknown) => setState({ status: "error", message: errorMessage(error) }));
  }, [token, queryClient]);

  if (state.status === "verifying") {
    return (
      <div className="grid justify-items-center gap-3 text-center" role="status">
        <Loader2 className="size-10 animate-spin text-teal-700" aria-hidden />
        <h1 className="text-2xl font-semibold text-navy-900">Confirming your email…</h1>
      </div>
    );
  }

  if (state.status === "done") {
    return (
      <div className="grid justify-items-center gap-4 text-center" role="status">
        <CheckCircle2 className="size-10 text-teal-700" aria-hidden />
        <div className="grid gap-1.5">
          <h1 className="text-2xl font-semibold text-navy-900">Email confirmed</h1>
          <p className="text-sm text-muted-foreground">Thanks. Your account is fully set up.</p>
        </div>
        <Button asChild size="lg" className="h-10 w-full">
          <Link href="/dashboard">Go to your dashboard</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid justify-items-center gap-4 text-center" role="alert">
      <XCircle className="size-10 text-destructive" aria-hidden />
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">We could not confirm your email</h1>
        <p className="text-sm text-muted-foreground">{state.message}</p>
        <p className="text-sm text-muted-foreground">
          Sign in and use “Resend email” on your dashboard to get a fresh link.
        </p>
      </div>
      <Button asChild variant="outline" size="lg" className="h-10 w-full">
        <Link href="/login?next=/dashboard">Sign in</Link>
      </Button>
    </div>
  );
}
