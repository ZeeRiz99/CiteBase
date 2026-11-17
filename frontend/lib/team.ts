import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { meQueryKey, type Role } from "@/lib/auth";

export type GrantableRole = Exclude<Role, "owner">;

export type Member = {
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
  joined_at: string;
  is_you: boolean;
};

export type Invitation = {
  id: string;
  email: string;
  role: GrantableRole;
  created_at: string;
  expires_at: string;
  link: string | null;
};

export type WorkspaceSettings = {
  id: string;
  name: string;
  slug: string;
  monthly_token_limit: number | null;
  token_limit_source: "workspace" | "default";
};

export type InvitationPreview = {
  email: string;
  role: GrantableRole;
  workspace_name: string;
  inviter_name: string | null;
  expires_at: string;
};

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

export const ROLE_HINTS: Record<GrantableRole, string> = {
  admin: "Manages documents, the team and insights",
  member: "Uploads documents and asks questions",
  viewer: "Asks questions only",
};

/** Roles an actor may grant: strictly below their own (mirrors app/services/team.py). */
export function grantableRoles(actor: Role | undefined): GrantableRole[] {
  if (!actor) return [];
  return (["admin", "member", "viewer"] as const).filter((r) => RANK[r] < RANK[actor]);
}

/** Whether an actor may change or remove someone: only people below their own role, never themselves. */
export function canManage(actor: Role | undefined, target: Member): boolean {
  return Boolean(actor) && !target.is_you && RANK[target.role] < RANK[actor as Role];
}

export const teamKeys = {
  workspace: ["workspace"] as const,
  members: ["workspace", "members"] as const,
  invitations: ["workspace", "invitations"] as const,
};

export function useWorkspaceSettings() {
  return useQuery({ queryKey: teamKeys.workspace, queryFn: () => api.get<WorkspaceSettings>("/api/v1/workspace") });
}

export function useRenameWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.patch<WorkspaceSettings>("/api/v1/workspace", { name }),
    onSuccess: (data) => {
      queryClient.setQueryData(teamKeys.workspace, data);
      void queryClient.invalidateQueries({ queryKey: meQueryKey });
    },
  });
}

export function useMembers(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.members,
    queryFn: () => api.get<Member[]>("/api/v1/workspace/members"),
    enabled,
  });
}

export function useInvitations(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.invitations,
    queryFn: () => api.get<Invitation[]>("/api/v1/workspace/invitations"),
    enabled,
  });
}

export function useInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: GrantableRole }) =>
      api.post<Invitation>("/api/v1/workspace/invitations", body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: teamKeys.invitations }),
  });
}

export function useRevokeInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/v1/workspace/invitations/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: teamKeys.invitations }),
  });
}

export function useChangeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: GrantableRole }) =>
      api.patch(`/api/v1/workspace/members/${userId}`, { role }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: teamKeys.members }),
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.delete<void>(`/api/v1/workspace/members/${userId}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: teamKeys.members }),
  });
}
