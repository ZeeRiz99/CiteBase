"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { UserMenu } from "@/components/app/user-menu";
import { VerifyEmailBanner } from "@/components/app/verify-email-banner";
import { NAV_ITEMS, isActive } from "@/components/app/nav-items";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api";
import { useMe, type Me } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me, error, refetch, isFetching } = useMe();
  const unauthenticated = isApiError(error) && error.status === 401;

  useEffect(() => {
    if (unauthenticated) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [unauthenticated, pathname, router]);

  if (error && !unauthenticated) {
    return (
      <div className="grid min-h-screen place-items-center p-6">
        <div className="grid max-w-sm justify-items-center gap-4 text-center" role="alert">
          <AlertTriangle className="size-10 text-warning" aria-hidden />
          <h1 className="text-xl font-semibold">We could not load your workspace</h1>
          <p className="text-sm text-muted-foreground">The server did not respond. Check your connection and try again.</p>
          <Button onClick={() => refetch()} disabled={isFetching}>
            <RotateCw className={cn(isFetching && "animate-spin")} aria-hidden /> Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!me) return <ShellSkeleton />;

  return (
    <div className="flex min-h-screen">
      <Sidebar pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar me={me} pathname={pathname} />
        {!me.user.email_verified ? <VerifyEmailBanner email={me.user.email} /> : null}
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 animate-fade-in px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground lg:flex">
      <div className="flex h-16 items-center px-5">
        <Link href="/dashboard" className="rounded-md">
          <Logo inverted />
        </Link>
      </div>
      <nav aria-label="Main" className="grid gap-1 px-3 py-4">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-white",
              )}
            >
              <Icon className={cn("size-4", active ? "text-teal-500" : "text-sidebar-foreground/80")} aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

function Topbar({ me, pathname }: { me: Me; pathname: string }) {
  return (
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/75">
      <div className="flex h-16 items-center gap-4 px-4 sm:px-6 lg:px-10">
        <Link href="/dashboard" className="lg:hidden">
          <Logo />
        </Link>
        <div className="hidden min-w-0 lg:block">
          <p className="truncate text-sm font-medium text-navy-900">{me.workspace.name}</p>
        </div>
        <div className="ml-auto">
          <UserMenu me={me} />
        </div>
      </div>
      <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-4 pb-2 sm:px-6 lg:hidden">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap",
                active ? "bg-navy-50 text-navy-900" : "text-muted-foreground hover:text-navy-900",
              )}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function ShellSkeleton() {
  return (
    <div className="flex min-h-screen" aria-busy="true" aria-label="Loading your workspace">
      <div className="hidden w-64 shrink-0 bg-sidebar lg:block" />
      <div className="flex-1">
        <div className="flex h-16 items-center border-b bg-white px-6">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="ml-auto size-8 rounded-full" />
        </div>
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-10">
          <Skeleton className="h-8 w-64" />
          <div className="grid gap-4 md:grid-cols-3">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        </div>
      </div>
    </div>
  );
}
