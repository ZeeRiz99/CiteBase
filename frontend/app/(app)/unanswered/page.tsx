import type { Metadata } from "next";

import { UnansweredView } from "@/components/insights/unanswered-view";

export const metadata: Metadata = { title: "Unanswered questions" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

export default function UnansweredPage() {
  return <UnansweredView />;
}
