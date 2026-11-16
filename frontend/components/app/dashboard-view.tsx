"use client";

import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Circle,
  FileCheck2,
  Files,
  Loader2,
  MessageCircleQuestion,
  MessagesSquare,
  ThumbsUp,
  Upload,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useResendVerification } from "@/components/app/verify-email-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { hasRole, useMe } from "@/lib/auth";
import { useUsage } from "@/lib/chat";
import { useDashboardSummary } from "@/lib/documents";

const ROLE_LABEL = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" } as const;

export function DashboardView() {
  const { data: me } = useMe();
  const summary = useDashboardSummary();
  const isAdmin = hasRole(me?.role, "admin");
  const usage = useUsage(isAdmin);
  const resend = useResendVerification();
  if (!me) return null; // the app shell renders the loading state

  const docs = summary.data?.documents;
  const questions = summary.data?.questions;
  const firstName = me.user.full_name.split(" ")[0];
  const steps: { label: string; done: boolean; action?: ReactNode }[] = [
    { label: "Create your workspace", done: true },
    {
      label: "Confirm your email address",
      done: me.user.email_verified,
      action: (
        <Button size="sm" variant="outline" onClick={() => resend.mutate()} disabled={resend.isPending}>
          {resend.isPending ? "Sending…" : "Resend email"}
        </Button>
      ),
    },
    {
      label: "Upload your first document",
      done: (docs?.total ?? 0) > 0,
      action: (
        <Button size="sm" asChild>
          <Link href="/knowledge-base">
            <Upload aria-hidden /> Upload
          </Link>
        </Button>
      ),
    },
    {
      label: "Ask your first question",
      done: (questions?.last_30d ?? 0) > 0,
      action: (
        <Button size="sm" asChild>
          <Link href="/chat">
            <MessagesSquare aria-hidden /> Ask
          </Link>
        </Button>
      ),
    },
  ];
  const completed = steps.filter((s) => s.done).length;

  return (
    <div className="grid gap-8">
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">Welcome, {firstName}</h1>
        <p className="text-muted-foreground">Here is the state of your workspace.</p>
      </div>

      <section aria-label="Document statistics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Documents" value={docs?.total} icon={<Files className="size-4" aria-hidden />} loading={summary.isPending} />
        <Stat label="Ready" value={docs?.indexed} icon={<FileCheck2 className="size-4" aria-hidden />} loading={summary.isPending} tone="teal" />
        <Stat label="Processing" value={docs?.processing} icon={<Loader2 className="size-4" aria-hidden />} loading={summary.isPending} />
        <Stat
          label="Needs attention"
          value={docs?.attention}
          icon={<AlertTriangle className="size-4" aria-hidden />}
          loading={summary.isPending}
          tone={(docs?.attention ?? 0) > 0 ? "amber" : undefined}
          href={(docs?.attention ?? 0) > 0 ? "/knowledge-base" : undefined}
        />
      </section>

      <section aria-label="Question statistics" className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Questions, last 7 days"
          value={questions?.last_7d}
          icon={<MessagesSquare className="size-4" aria-hidden />}
          loading={summary.isPending}
          href="/chat"
        />
        <Stat
          label="Unanswered, open"
          value={questions?.unanswered_open}
          icon={<MessageCircleQuestion className="size-4" aria-hidden />}
          loading={summary.isPending}
          tone={(questions?.unanswered_open ?? 0) > 0 ? "amber" : undefined}
          href={isAdmin ? "/unanswered" : undefined}
        />
        <Stat
          label={questions?.rated ? `Rated helpful ( rated)` : "Rated helpful"}
          value={questions?.helpful_rate === null || questions?.helpful_rate === undefined ? undefined : Math.round(questions.helpful_rate * 100)}
          suffix={questions?.helpful_rate === null ? undefined : "%"}
          empty="No ratings yet"
          icon={<ThumbsUp className="size-4" aria-hidden />}
          loading={summary.isPending}
          tone="teal"
        />
      </section>

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
                  {!step.done && step.action ? <span className="ml-auto">{step.action}</span> : null}
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
            {isAdmin && usage.data ? <UsageMeter used={usage.data.tokens_used} limit={usage.data.token_limit} /> : null}
            <p className="text-xs text-muted-foreground">
              Your data is isolated from every other workspace at the database level.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

function UsageMeter({ used, limit }: { used: number; limit: number | null }) {
  const share = limit ? Math.min(1, used / limit) : 0;
  return (
    <div className="grid gap-1.5">
      <p className="text-muted-foreground">AI usage this month</p>
      <p className="font-medium text-navy-900">
        {compact.format(used)} tokens{limit ? ` of ${compact.format(limit)}` : " (no limit)"}
      </p>
      {limit ? (
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label="AI usage this month"
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={used}
        >
          <div
            className={share > 0.9 ? "h-full rounded-full bg-warning" : "h-full rounded-full bg-teal-600"}
            style={{ width: `${Math.max(share * 100, used > 0 ? 2 : 0)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
  loading,
  tone,
  href,
  suffix,
  empty,
}: {
  label: string;
  value: number | undefined;
  icon: ReactNode;
  loading: boolean;
  tone?: "teal" | "amber";
  href?: string;
  suffix?: string;
  empty?: string; // shown instead of 0 when there is no value yet
}) {
  const body = (
    <Card className="h-full gap-2 py-4 shadow-soft">
      <CardContent className="grid gap-1 px-4">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className={tone === "teal" ? "text-teal-700" : tone === "amber" ? "text-warning" : "text-navy-600"}>{icon}</span>
          {label}
        </p>
        {loading ? (
          <Skeleton className="h-8 w-12" />
        ) : value === undefined && empty ? (
          <p className="py-1.5 text-sm text-muted-foreground">{empty}</p>
        ) : (
          <p className="text-3xl font-semibold text-navy-900">
            {value ?? 0}
            {suffix ? <span className="text-xl">{suffix}</span> : null}
          </p>
        )}
      </CardContent>
    </Card>
  );
  return href ? (
    <Link href={href} className="rounded-xl">
      {body}
    </Link>
  ) : (
    body
  );
}
