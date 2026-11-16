import type { Metadata } from "next";
import { Suspense } from "react";

import { SourcePageView } from "@/components/chat/source-page-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Source" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

export default function SourcePage({ params }: PageProps<"/sources/[chunkId]">) {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      {params.then(({ chunkId }) => (
        <SourcePageView chunkId={chunkId} />
      ))}
    </Suspense>
  );
}
