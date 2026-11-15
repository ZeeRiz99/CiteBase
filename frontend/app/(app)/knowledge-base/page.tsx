import type { Metadata } from "next";

import { KnowledgeBaseView } from "@/components/documents/knowledge-base-view";

export const metadata: Metadata = { title: "Knowledge base" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

export default function KnowledgeBasePage() {
  return <KnowledgeBaseView />;
}
