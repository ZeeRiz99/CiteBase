"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { meQueryKey, type Message } from "@/lib/auth";

type State = { status: "working" } | { status: "done"; message: string } | { status: "error"; message: string };

export function ConfirmEmailChange() {
  const token = useSearchParams().get("token");
  const queryClient = useQueryClient();
  const [state, setState] = useState<State>(
    token ? { status: "working" } : { status: "error", message: "This link is missing its token." },
  );
  const started = useRef(false); // single-use token: run once even in development's double effects

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    api
      .post<Message>("/api/v1/auth/confirm-email-change", { token })
      .then((result) => {
        queryClient.removeQueries({ queryKey: meQueryKey }); // every session was signed out
        setState({ status: "done", message: result.message });
      })
      .catch((error: unknown) => setState({ status: "error", message: errorMessage(error) }));
  }, [token, queryClient]);

  if (state.status === "working") {
    return (
      <div className="grid justify-items-center gap-3 text-center" role="status">
        <Loader2 className="size-10 animate-spin text-teal-700" aria-hidden />
        <h1 className="text-2xl font-semibold text-navy-900">Changing your email…</h1>
      </div>
    );
  }

  if (state.status === "done") {
    return (
      <div className="grid justify-items-center gap-4 text-center" role="status">
        <CheckCircle2 className="size-10 text-teal-700" aria-hidden />
        <div className="grid gap-1.5">
          <h1 className="text-2xl font-semibold text-navy-900">Email changed</h1>
          <p className="text-sm text-muted-foreground">{state.message}</p>
          <p className="text-sm text-muted-foreground">For your security, every device was signed out.</p>
        </div>
        <Button asChild size="lg" className="h-10 w-full">
          <Link href="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid justify-items-center gap-4 text-center" role="alert">
      <XCircle className="size-10 text-destructive" aria-hidden />
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">We could not change your email</h1>
        <p className="text-sm text-muted-foreground">{state.message}</p>
        <p className="text-sm text-muted-foreground">
          Links expire and work once. Request the change again under Settings.
        </p>
      </div>
      <Button asChild variant="outline" size="lg" className="h-10 w-full">
        <Link href="/settings">Go to Settings</Link>
      </Button>
    </div>
  );
}
