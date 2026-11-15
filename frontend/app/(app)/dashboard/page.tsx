import type { Metadata } from "next";

import { DashboardView } from "@/components/app/dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

export default function DashboardPage() {
  return <DashboardView />;
}
