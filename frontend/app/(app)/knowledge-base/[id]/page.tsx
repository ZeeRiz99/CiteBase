import type { Metadata } from "next";
import { Suspense } from "react";

import { DocumentDetailView } from "@/components/documents/document-detail-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Document" };
// Client-rendered behind the auth shell; see app/(app)/layout.tsx.
export const instant = false;

// With Cache Components, runtime params are read inside a Suspense boundary.
export default function DocumentPage({ params }: PageProps<"/knowledge-base/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-40" />}>
      {params.then(({ id }) => (
        <DocumentDetailView id={id} />
      ))}
    </Suspense>
  );
}
