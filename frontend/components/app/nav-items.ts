import { LayoutDashboard, Library, MessageCircleQuestion, MessagesSquare, Settings, type LucideIcon } from "lucide-react";

import type { Role } from "@/lib/auth";

export type NavItem = { href: string; label: string; icon: LucideIcon; minRole?: Role };

// Only screens that exist. minRole hides links the user cannot use (the server enforces roles).
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessagesSquare },
  { href: "/knowledge-base", label: "Knowledge base", icon: Library },
  { href: "/unanswered", label: "Unanswered", icon: MessageCircleQuestion, minRole: "admin" },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
