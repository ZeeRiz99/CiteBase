import { BadgeCheck, FileSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { branding } from "@/lib/branding";

const POINTS = [
  { icon: FileSearch, text: "Answers come from your own documents, not the open internet." },
  { icon: BadgeCheck, text: "Every answer links to the page and passage it came from." },
  { icon: ShieldCheck, text: "When the documents do not say, it tells you so." },
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden overflow-hidden bg-navy-900 p-10 text-white lg:flex lg:flex-col">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(20,184,166,0.22),transparent_45%),radial-gradient(circle_at_90%_90%,rgba(34,211,238,0.14),transparent_40%)]"
        />
        <Link href="/" className="relative w-fit rounded-md">
          <Logo inverted />
        </Link>
        <div className="relative mt-auto grid max-w-md gap-8">
          <p className="text-3xl leading-tight font-semibold">{branding.tagline}</p>
          <ul className="grid gap-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-[15px] text-navy-100">
                <Icon className="mt-0.5 size-5 shrink-0 text-teal-500" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>
      </aside>
      <main id="main" className="flex flex-col px-4 py-8 sm:px-8">
        <Link href="/" className="mb-10 w-fit rounded-md lg:hidden">
          <Logo />
        </Link>
        <div className="mx-auto my-auto w-full max-w-sm animate-fade-in">{children}</div>
      </main>
    </div>
  );
}
