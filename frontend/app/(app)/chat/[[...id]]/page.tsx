import type { Metadata } from "next";
import { Suspense } from "react";

import { ChatView } from "@/components/chat/chat-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Chat" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

// One page for /chat and /chat/<id>: the view reads the id from the URL and switches
// conversations with history.pushState, so a streaming answer is never remounted.
export default function ChatPage() {
  return (
    <Suspense fallback={<Skeleton className="m-6 h-64" />}>
      <ChatView />
    </Suspense>
  );
}
