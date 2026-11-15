import { Suspense, type ReactNode } from "react";

import { AppShell, ShellSkeleton } from "@/components/app/app-shell";

// The signed-in area renders on the client after an auth check (/me), so navigation into it is
// allowed to wait; opt out of instant-navigation validation for this segment.
export const instant = false;

// The shell reads the URL (usePathname). With Cache Components that must sit inside Suspense,
// otherwise dynamic routes such as /knowledge-base/[id] cannot be prerendered.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<ShellSkeleton />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
