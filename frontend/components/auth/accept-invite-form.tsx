"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { api, errorMessage, isApiError } from "@/lib/api";
import { meQueryKey } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";
import { acceptInviteSchema, type AcceptInviteValues } from "@/lib/schemas";
import { ROLE_HINTS, ROLE_LABELS, type InvitationPreview } from "@/lib/team";

export function AcceptInviteForm() {
  const token = useSearchParams().get("token");
  if (!token) {
    return <Unusable message="This invitation link is missing its token. Open the link from your email again." />;
  }
  return <AcceptInvite token={token} />;
}

function Unusable({ message }: { message: string }) {
  return (
    <div className="grid gap-5">
      <h1 className="text-2xl font-semibold text-navy-900">Invitation unavailable</h1>
      <FormAlert message={message} />
      <p className="text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-teal-700 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const preview = useQuery({
    queryKey: ["invitation-preview", token],
    queryFn: () => api.post<InvitationPreview>("/api/v1/invitations/preview", { token }),
    retry: false,
    staleTime: Infinity,
  });
  const form = useForm<AcceptInviteValues>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: { full_name: "", password: "", confirm: "" },
  });
  const { errors, isSubmitting } = form.formState;

  if (preview.isPending) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Checking your invitation…
      </p>
    );
  }
  if (preview.isError) {
    const expired = isApiError(preview.error) && preview.error.code === "invalid_token";
    return (
      <Unusable
        message={
          expired
            ? "This invitation is no longer valid. It may have expired, been used or been cancelled. Ask your workspace admin for a new one."
            : errorMessage(preview.error)
        }
      />
    );
  }
  const invitation = preview.data;

  async function onSubmit(values: AcceptInviteValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/invitations/accept", { token, full_name: values.full_name, password: values.password });
      await queryClient.invalidateQueries({ queryKey: meQueryKey });
      toast.success(`Welcome to ${invitation.workspace_name}`);
      router.replace("/dashboard");
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["full_name", "password"]));
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">Join {invitation.workspace_name}</h1>
        <p className="text-sm text-muted-foreground">
          {invitation.inviter_name ? `${invitation.inviter_name} invited you` : "You were invited"} as{" "}
          <span className="font-medium text-navy-900">{ROLE_LABELS[invitation.role].toLowerCase()}</span>:{" "}
          {ROLE_HINTS[invitation.role].toLowerCase()}.
        </p>
      </div>
      <FormAlert message={formError} />
      <TextField id="email" label="Email" value={invitation.email} readOnly disabled />
      <TextField
        id="full_name"
        label="Your name"
        autoComplete="name"
        error={errors.full_name?.message}
        {...form.register("full_name")}
      />
      <TextField
        id="password"
        label="Choose a password"
        type="password"
        autoComplete="new-password"
        hint="At least 10 characters. A short phrase is easier to remember."
        error={errors.password?.message}
        {...form.register("password")}
      />
      <TextField
        id="confirm"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        error={errors.confirm?.message}
        {...form.register("confirm")}
      />
      <Button type="submit" size="lg" className="h-10" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {isSubmitting ? "Joining…" : "Accept and join"}
      </Button>
    </form>
  );
}
