"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { applyServerErrors } from "@/lib/form-errors";
import { resetPasswordSchema, type ResetPasswordValues } from "@/lib/schemas";

export function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirm: "" },
  });
  const { errors, isSubmitting } = form.formState;

  if (!token) {
    return (
      <div className="grid gap-5">
        <h1 className="text-2xl font-semibold text-navy-900">Link incomplete</h1>
        <FormAlert message="This reset link is missing its token. Open the link from your email again, or request a new one." />
        <Button asChild size="lg" className="h-10">
          <Link href="/forgot-password">Request a new link</Link>
        </Button>
      </div>
    );
  }

  async function onSubmit(values: ResetPasswordValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/auth/reset-password", { token, password: values.password });
      toast.success("Password updated", { description: "Sign in with your new password." });
      router.replace("/login");
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["password"]));
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">Choose a new password</h1>
        <p className="text-sm text-muted-foreground">You will be signed out of every other device.</p>
      </div>
      <FormAlert message={formError} />
      {formError ? (
        <Link href="/forgot-password" className="text-sm font-medium text-teal-700 hover:underline">
          Request a new reset link
        </Link>
      ) : null}
      <TextField
        id="password"
        label="New password"
        type="password"
        autoComplete="new-password"
        hint="At least 10 characters."
        error={errors.password?.message}
        {...form.register("password")}
      />
      <TextField
        id="confirm"
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        error={errors.confirm?.message}
        {...form.register("confirm")}
      />
      <Button type="submit" size="lg" className="h-10" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {isSubmitting ? "Saving…" : "Update password"}
      </Button>
    </form>
  );
}
