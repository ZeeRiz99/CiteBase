import type { Metadata } from "next";

import { SettingsView } from "@/components/app/settings-view";

export const metadata: Metadata = { title: "Settings" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

export default function SettingsPage() {
  return <SettingsView />;
}
