"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Copy, Loader2, Mail, Trash2, UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { ConfirmEmailNotice } from "@/components/app/confirm-email-notice";
import { FormAlert } from "@/components/forms/form-alert";
import { TextField } from "@/components/forms/text-field";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { errorMessage, isApiError } from "@/lib/api";
import { hasRole, needsEmailConfirmation, type Me } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";
import { inviteSchema, workspaceSchema, type InviteValues, type WorkspaceValues } from "@/lib/schemas";
import {
  canManage,
  grantableRoles,
  ROLE_HINTS,
  ROLE_LABELS,
  useChangeRole,
  useInvitations,
  useInvite,
  useMembers,
  useRemoveMember,
  useRenameWorkspace,
  useRevokeInvitation,
  useWorkspaceSettings,
  type GrantableRole,
  type Member,
} from "@/lib/team";

const SELECT =
  "h-10 rounded-md border border-input bg-white px-3 text-[15px] text-navy-900 shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50";

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/* ---- Workspace -------------------------------------------------------------------------- */

export function WorkspaceCard({ me }: { me: Me }) {
  const isAdmin = hasRole(me.role, "admin");
  const { data: settings } = useWorkspaceSettings();
  const rename = useRenameWorkspace();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<WorkspaceValues>({
    resolver: zodResolver(workspaceSchema),
    values: { name: settings?.name ?? me.workspace.name },
  });
  const { errors, isSubmitting, isDirty } = form.formState;

  async function onSubmit(values: WorkspaceValues) {
    setFormError(null);
    try {
      await rename.mutateAsync(values.name);
      toast.success("Workspace renamed");
    } catch (error) {
      setFormError(applyServerErrors(error, form.setError, ["name"]));
    }
  }

  const allowance =
    settings === undefined
      ? "…"
      : settings.monthly_token_limit === null
        ? "Unlimited"
        : `${settings.monthly_token_limit.toLocaleString()} tokens per month`;

  return (
    <Card className="shadow-soft">
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <CardHeader>
          <CardTitle className="text-base">Workspace</CardTitle>
          <CardDescription>The shared space for your team&apos;s documents and answers.</CardDescription>
        </CardHeader>
        <CardContent className="grid max-w-md gap-4">
          <FormAlert message={formError} />
          {isAdmin ? (
            <TextField id="workspace_name" label="Workspace name" error={errors.name?.message} {...form.register("name")} />
          ) : null}
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            {!isAdmin ? (
              <div>
                <dt className="text-muted-foreground">Name</dt>
                <dd className="font-medium text-navy-900">{me.workspace.name}</dd>
              </div>
            ) : null}
            <div>
              <dt className="text-muted-foreground">Workspace ID</dt>
              <dd className="font-mono text-xs text-navy-900">{me.workspace.slug}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">AI allowance</dt>
              <dd className="font-medium text-navy-900">{allowance}</dd>
            </div>
          </dl>
          {isAdmin ? (
            <p className="text-xs text-muted-foreground">
              The AI allowance is set by whoever runs this installation. Ask them to change it.
            </p>
          ) : null}
        </CardContent>
        {isAdmin ? (
          <CardFooter className="mt-6 border-t pt-6">
            <Button type="submit" disabled={isSubmitting || !isDirty}>
              {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Save workspace
            </Button>
          </CardFooter>
        ) : null}
      </form>
    </Card>
  );
}

/* ---- Team ------------------------------------------------------------------------------- */

export function TeamCard({ me }: { me: Me }) {
  const members = useMembers(true);
  const invitations = useInvitations(true);
  const roles = grantableRoles(me.role);

  return (
    <Card id="team" className="shadow-soft scroll-mt-24">
      <CardHeader>
        <CardTitle className="text-base">Team</CardTitle>
        <CardDescription>Invite people and choose what they can do. You can manage roles below your own.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-8">
        {needsEmailConfirmation(me) ? (
          <ConfirmEmailNotice email={me.user.email} action="invite people" />
        ) : (
          <InviteForm roles={roles} />
        )}

        <section aria-labelledby="members-heading" className="grid gap-3">
          <h3 id="members-heading" className="text-sm font-semibold text-navy-900">
            Members{members.data ? ` (${members.data.length})` : ""}
          </h3>
          {members.isPending ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : members.isError ? (
            <FormAlert message={errorMessage(members.error)} />
          ) : (
            <ul className="divide-y rounded-xl border">
              {members.data.map((m) => (
                <MemberRow key={m.user_id} member={m} me={me} roles={roles} />
              ))}
            </ul>
          )}
        </section>

        {invitations.data && invitations.data.length > 0 ? (
          <section aria-labelledby="pending-heading" className="grid gap-3">
            <h3 id="pending-heading" className="text-sm font-semibold text-navy-900">
              Pending invitations ({invitations.data.length})
            </h3>
            <ul className="divide-y rounded-xl border">
              {invitations.data.map((inv) => (
                <PendingRow key={inv.id} id={inv.id} email={inv.email} role={inv.role} expires={inv.expires_at} />
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
    </Card>
  );
}

function InviteForm({ roles }: { roles: GrantableRole[] }) {
  const invite = useInvite();
  const [formError, setFormError] = useState<string | null>(null);
  const [lastLink, setLastLink] = useState<{ email: string; link: string; expires: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const form = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", role: roles.includes("member") ? "member" : (roles[0] ?? "viewer") },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: InviteValues) {
    setFormError(null);
    setCopied(false);
    try {
      const created = await invite.mutateAsync(values);
      setLastLink(created.link ? { email: created.email, link: created.link, expires: created.expires_at } : null);
      form.reset({ email: "", role: values.role });
      toast.success("Invitation sent", { description: `We emailed ${created.email} a link to join.` });
    } catch (error) {
      if (isApiError(error) && error.code === "email_taken") {
        form.setError("email", { type: "server", message: error.message });
        return;
      }
      setFormError(applyServerErrors(error, form.setError, ["email", "role"]));
    }
  }

  async function copyLink() {
    if (!lastLink) return;
    try {
      await navigator.clipboard.writeText(lastLink.link);
      setCopied(true);
    } catch {
      toast.error("Could not copy. Select the link and copy it manually.");
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-3">
      <FormAlert message={formError} />
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        <TextField
          id="invite_email"
          label="Invite by email"
          type="email"
          autoComplete="off"
          placeholder="colleague@company.com"
          error={errors.email?.message}
          {...form.register("email")}
        />
        <div className="grid gap-1.5">
          <Label htmlFor="invite_role" className="text-sm font-medium text-navy-900">
            Role
          </Label>
          <select id="invite_role" className={SELECT} {...form.register("role")}>
            {roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" className="h-10" disabled={isSubmitting}>
          {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : <UserPlus aria-hidden />}
          Send invite
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        {roles.map((r) => `${ROLE_LABELS[r]}: ${ROLE_HINTS[r].toLowerCase()}`).join(". ")}.
      </p>
      {lastLink ? (
        <div className="grid gap-2 rounded-xl border border-dashed bg-muted/40 p-3 text-sm">
          <p className="text-slate-body">
            If the email does not arrive, send {lastLink.email} this link yourself. It works once and expires on {formatDate(lastLink.expires)}.
          </p>
          <div className="flex gap-2">
            <code className="min-w-0 flex-1 truncate rounded-md bg-white px-2 py-1.5 text-xs">{lastLink.link}</code>
            <Button type="button" size="sm" variant="outline" onClick={copyLink}>
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
              {copied ? "Copied" : "Copy link"}
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  );
}

function MemberRow({ member, me, roles }: { member: Member; me: Me; roles: GrantableRole[] }) {
  const changeRole = useChangeRole();
  const remove = useRemoveMember();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const manageable = canManage(me.role, member);

  async function onRole(role: GrantableRole) {
    try {
      await changeRole.mutateAsync({ userId: member.user_id, role });
      toast.success(`${member.full_name} is now ${ROLE_LABELS[role].toLowerCase()}`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function onRemove() {
    try {
      await remove.mutateAsync(member.user_id);
      setConfirmOpen(false);
      toast.success(`${member.full_name} was removed`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-navy-900">
          {member.full_name}
          {member.is_you ? <span className="ml-1.5 font-normal text-muted-foreground">(you)</span> : null}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {member.email} · joined {formatDate(member.joined_at)}
        </p>
      </div>
      {manageable ? (
        <>
          <select
            aria-label={`Role for ${member.full_name}`}
            className={`${SELECT} h-9 text-sm`}
            value={member.role}
            disabled={changeRole.isPending}
            onChange={(e) => void onRole(e.target.value as GrantableRole)}
          >
            {roles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={`Remove ${member.full_name}`}
            onClick={() => setConfirmOpen(true)}
          >
            <Trash2 aria-hidden />
          </Button>
          <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remove {member.full_name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  They are signed out right away and can no longer open this workspace. Documents they uploaded
                  stay in the knowledge base.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={(e) => {
                    e.preventDefault();
                    void onRemove();
                  }}
                  disabled={remove.isPending}
                  className="bg-destructive text-white hover:bg-destructive/90"
                >
                  {remove.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
                  Remove
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      ) : (
        <Badge variant="secondary">{ROLE_LABELS[member.role]}</Badge>
      )}
    </li>
  );
}

function PendingRow({ id, email, role, expires }: { id: string; email: string; role: GrantableRole; expires: string }) {
  const revoke = useRevokeInvitation();
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <Mail className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-navy-900">{email}</p>
        <p className="text-xs text-muted-foreground">
          {ROLE_LABELS[role]} · expires {formatDate(expires)}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={revoke.isPending}
        onClick={() =>
          revoke.mutate(id, {
            onSuccess: () => toast.success("Invitation cancelled"),
            onError: (error) => toast.error(errorMessage(error)),
          })
        }
      >
        Cancel invite
      </Button>
    </li>
  );
}
