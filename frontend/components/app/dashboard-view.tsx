"use client";

import { CheckCircle2, Circle, KeyRound, ShieldCheck, Building2 } from "lucide-react";
import Link from "next/link";

import { useResendVerification } from "@/components/app/verify-email-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/lib/auth";

const ROLE_LABEL = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" } as const;

export function DashboardView() {
  const { data: me } = useMe();
  const resend = useResendVerification();
  if (!me) return null; // the app shell renders the loading state

  const firstName = me.user.full_name.split(" ")[0];
  const steps = [
    { label: "Create your workspace", done: true },
    { label: "Confirm your email address", done: me.user.email_verified },
  ];
  const completed = steps.filter((s) => s.done).length;

  return (
    <div className="grid gap-8">
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">Welcome, {firstName}</h1>
        <p className="text-muted-foreground">Here is the state of your workspace.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="shadow-soft md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Getting started</CardTitle>
            <CardDescription>
              {completed} of {steps.length} complete
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div
              className="h-1.5 overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={steps.length}
              aria-valuenow={completed}
              aria-label="Setup progress"
            >
              <div className="h-full rounded-full bg-teal-600 transition-all" style={{ width: `${(completed / steps.length) * 100}%` }} />
            </div>
            <ul className="grid gap-2">
              {steps.map((step) => (
                <li key={step.label} className="flex items-center gap-3 rounded-lg border bg-white px-3 py-2.5">
                  {step.done ? (
                    <CheckCircle2 className="size-5 text-teal-600" aria-label="Done" />
                  ) : (
                    <Circle className="size-5 text-muted-foreground" aria-label="Not done" />
                  )}
                  <span className={step.done ? "text-sm text-muted-foreground line-through" : "text-sm font-medium"}>
                    {step.label}
                  </span>
                  {!step.done ? (
                    <Button size="sm" variant="outline" className="ml-auto" onClick={() => resend.mutate()} disabled={resend.isPending}>
                      {resend.isPending ? "Sending…" : "Resend email"}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Building2 className="size-4 text-teal-700" aria-hidden /> Workspace
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div>
              <p className="text-muted-foreground">Name</p>
              <p className="font-medium text-navy-900">{me.workspace.name}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Your role</p>
              <Badge variant="secondary" className="mt-1">
                {ROLE_LABEL[me.role]}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-soft">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="size-4 text-teal-700" aria-hidden /> Account security
          </CardTitle>
          <CardDescription>
            Your workspace data is isolated from every other workspace at the database level.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link href="/settings#password">
              <KeyRound aria-hidden /> Change password
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
