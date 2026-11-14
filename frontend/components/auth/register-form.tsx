"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { api, isApiError } from "@/lib/api";
import { meQueryKey, useRedirectIfSignedIn } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";
import { registerSchema, type RegisterValues } from "@/lib/schemas";

export function RegisterForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  useRedirectIfSignedIn("/dashboard");

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: "", workspace_name: "", email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: RegisterValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/auth/register", {
        ...values,
        workspace_name: values.workspace_name || null,
      });
      await queryClient.invalidateQueries({ queryKey: meQueryKey });
      toast.success("Account created", { description: "Check your inbox to confirm your email address." });
      router.replace("/dashboard");
    } catch (error) {
      if (isApiError(error) && error.code === "email_taken") {
        form.setError("email", { type: "server", message: error.message });
        return;
      }
      setFormError(applyServerErrors(error, form.setError, ["full_name", "workspace_name", "email", "password"]));
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-5">
      <div className="grid gap-1.5">
        <h1 className="text-2xl font-semibold text-navy-900">Create your account</h1>
        <p className="text-sm text-muted-foreground">Set up a private workspace for your documents.</p>
      </div>
      <FormAlert message={formError} />
      <TextField
        id="full_name"
        label="Your name"
        autoComplete="name"
        error={errors.full_name?.message}
        {...form.register("full_name")}
      />
      <TextField
        id="workspace_name"
        label="Company or team (optional)"
        autoComplete="organization"
        placeholder="Acme Ltd"
        error={errors.workspace_name?.message}
        {...form.register("workspace_name")}
      />
      <TextField
        id="email"
        label="Work email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...form.register("email")}
      />
      <TextField
        id="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        hint="At least 10 characters. A short phrase is easier to remember."
        error={errors.password?.message}
        {...form.register("password")}
      />
      <Button type="submit" size="lg" className="h-10" disabled={isSubmitting}>
        {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-teal-700 hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
