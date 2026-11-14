"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { meQueryKey, safeNextPath, useRedirectIfSignedIn } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";
import { loginSchema, type LoginValues } from "@/lib/schemas";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const next = safeNextPath(params.get("next"));
  const [formError, setFormError] = useState<string | null>(null);
  useRedirectIfSignedIn(next);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: LoginValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/auth/login", values);
      await queryClient.invalidateQueries({ queryKey: meQueryKey });
      router.replace(next);
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["email", "password"]));
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">Sign in</h1>
        <p className="text-sm text-muted-foreground">Welcome back. Sign in to your workspace.</p>
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
      <div className="grid gap-1.5">
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...form.register("password")}
        />
        <Link href="/forgot-password" className="justify-self-end text-sm font-medium text-teal-700 hover:underline">
          Forgot password?
        </Link>
      </div>
      <Button type="submit" size="lg" className="h-10" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        New here?{" "}
        <Link href="/register" className="font-medium text-teal-700 hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}
