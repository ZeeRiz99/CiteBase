"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { api, isApiError } from "@/lib/api";
import { TeamCard, WorkspaceCard } from "@/components/app/workspace-settings";
import { hasRole, meQueryKey, useMe, type Me } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";
import {
  changeEmailSchema,
  changePasswordSchema,
  profileSchema,
  type ChangeEmailValues,
  type ChangePasswordValues,
  type ProfileValues,
} from "@/lib/schemas";

export function SettingsView() {
  const { data: me } = useMe();
  if (!me) return null;
  return (
    <div className="grid gap-8">
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold text-navy-900 sm:text-3xl">Settings</h1>
        <p className="text-muted-foreground">
          {hasRole(me.role, "admin")
            ? "Manage your profile, sign-in security, workspace and team."
            : "Manage your profile and sign-in security."}
        </p>
      </div>
      <ProfileCard me={me} />
      <EmailCard me={me} />
      <PasswordCard />
      <WorkspaceCard me={me} />
      {hasRole(me.role, "admin") ? <TeamCard me={me} /> : null}
    </div>
  );
}

function ProfileCard({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    values: { full_name: me.user.full_name },
  });
  const { errors, isSubmitting, isDirty } = form.formState;

  async function onSubmit(values: ProfileValues) {
    setFormError(null);
    try {
      const updated = await api.patch<Me>("/api/v1/me", values);
      queryClient.setQueryData(meQueryKey, updated);
      toast.success("Profile saved");
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["full_name"]));
    }
  }

  return (
    <Card className="shadow-soft">
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
          <CardDescription>How your name appears to your team.</CardDescription>
        </CardHeader>
        <CardContent className="grid max-w-md gap-4">
          <FormAlert message={formError} />
          <TextField id="full_name" label="Full name" autoComplete="name" error={errors.full_name?.message} {...form.register("full_name")} />
        </CardContent>
        <CardFooter className="mt-6 border-t pt-6">
          <Button type="submit" disabled={isSubmitting || !isDirty}>
            {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Save profile
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function EmailCard({ me }: { me: Me }) {
  const [formError, setFormError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const form = useForm<ChangeEmailValues>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: { new_email: "", current_password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: ChangeEmailValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/me/email", values);
      setSentTo(values.new_email.trim().toLowerCase());
      form.reset();
    } catch (error) {
      if (isApiError(error) && (error.code === "email_taken" || error.code === "same_email")) {
        form.setError("new_email", { type: "server", message: error.message });
        return;
      }
      if (isApiError(error) && error.code === "wrong_password") {
        form.setError("current_password", { type: "server", message: error.message });
        return;
      }
      setFormError(applyServerErrors(error, form.setError, ["new_email", "current_password"]));
    }
  }

  return (
    <Card id="email" className="shadow-soft scroll-mt-24">
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <CardHeader>
          <CardTitle className="text-base">Sign-in email</CardTitle>
          <CardDescription>
            You sign in with <span className="font-medium text-navy-900">{me.user.email}</span>
            {me.user.email_verified ? " (confirmed)." : " (not confirmed yet)."} To change it, we send a link to the
            new address; it changes once you open that link.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid max-w-md gap-4">
          <FormAlert message={formError} />
          {sentTo ? (
            <p className="rounded-xl border border-teal-100 bg-teal-50 px-4 py-3 text-sm text-teal-900" role="status">
              We sent a confirmation link to <span className="font-medium">{sentTo}</span>. Your sign-in email stays the
              same until you open it, then every device is signed out.
            </p>
          ) : null}
          <TextField id="new_email" label="New email" type="email" autoComplete="email" error={errors.new_email?.message} {...form.register("new_email")} />
          <TextField id="email_password" label="Current password" type="password" autoComplete="current-password" error={errors.current_password?.message} {...form.register("current_password")} />
        </CardContent>
        <CardFooter className="mt-6 border-t pt-6">
          <Button type="submit" variant="outline" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Send confirmation link
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: ChangePasswordValues) {
    setFormError(null);
    try {
      await api.post("/api/v1/me/password", {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      form.reset();
      toast.success("Password updated", { description: "Other devices have been signed out." });
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["current_password", "new_password"]));
    }
  }

  return (
    <Card id="password" className="shadow-soft scroll-mt-24">
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <CardHeader>
          <CardTitle className="text-base">Password</CardTitle>
          <CardDescription>Changing your password signs you out on every other device.</CardDescription>
        </CardHeader>
        <CardContent className="grid max-w-md gap-4">
          <FormAlert message={formError} />
          <TextField id="current_password" label="Current password" type="password" autoComplete="current-password" error={errors.current_password?.message} {...form.register("current_password")} />
          <TextField id="new_password" label="New password" type="password" autoComplete="new-password" hint="At least 10 characters." error={errors.new_password?.message} {...form.register("new_password")} />
          <TextField id="confirm" label="Confirm new password" type="password" autoComplete="new-password" error={errors.confirm?.message} {...form.register("confirm")} />
        </CardContent>
        <CardFooter className="mt-6 border-t pt-6">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Update password
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
