"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { applyServerErrors } from "@/lib/form-errors";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/lib/schemas";

export function ForgotPasswordForm() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: ForgotPasswordValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/auth/forgot-password", values);
      setSentTo(values.email);
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["email"]));
    }
  }

  if (sentTo) {
    return (
      <div className="grid gap-5 text-center" role="status">
        <MailCheck className="mx-auto size-10 text-teal-700" aria-hidden />
        <div className="grid gap-1.5">
          <h1 className="text-2xl font-semibold text-navy-900">Check your email</h1>
          <p className="text-sm text-muted-foreground">
            If an account exists for <span className="font-medium text-navy-900">{sentTo}</span>, a reset link is on
            its way. It expires in 60 minutes.
          </p>
        </div>
        <Button asChild variant="outline" size="lg" className="h-10">
          <Link href="/login">Back to sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">Reset your password</h1>
        <p className="text-sm text-muted-foreground">Enter your email and we will send you a reset link.</p>
      </div>
      <FormAlert message={formError} />
      <TextField
        id="email"
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...form.register("email")}
      />
      <Button type="submit" size="lg" className="h-10" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {isSubmitting ? "Sending…" : "Send reset link"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link href="/login" className="font-medium text-teal-700 hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
