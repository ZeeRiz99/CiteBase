"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, readCookie } from "@/lib/api";

const SESSION_MARKER = "cb_session";

export type Role = "owner" | "admin" | "member" | "viewer";

export type Me = {
  user: { id: string; email: string; full_name: string; email_verified: boolean };
  workspace: { id: string; name: string; slug: string };
  role: Role;
};

export type Message = { message: string };

const ROLE_RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

/** UI hint only: the server enforces every role check. */
export function hasRole(role: Role | undefined, minimum: Role): boolean {
  return role !== undefined && ROLE_RANK[role] >= ROLE_RANK[minimum];
}

export const meQueryKey = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: () => api.get<Me>("/api/v1/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
}

/** On guest-only pages: if a session exists, go to `target` instead of showing the form. */
export function useRedirectIfSignedIn(target: string) {
  const router = useRouter();
  const [hasSession] = useState(() => readCookie(SESSION_MARKER) === "1");
  const me = useQuery({
    queryKey: meQueryKey,
    queryFn: () => api.get<Me>("/api/v1/auth/me"),
    enabled: hasSession,
    retry: false,
  });
  useEffect(() => {
    if (me.data) router.replace(target);
  }, [me.data, router, target]);
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => api.post<Message>("/api/v1/auth/logout"),
    onSettled: () => {
      queryClient.clear();
      router.replace("/login");
    },
  });
}

/** Only allow same-site relative redirects after sign-in (prevents open redirects). */
export function safeNextPath(next: string | null | undefined, fallback = "/dashboard"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}
