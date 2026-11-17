import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Building2,
  FileQuestion,
  FileText,
  GraduationCap,
  Headset,
  LockKeyhole,
  MessageSquareText,
  Scale,
  ShieldCheck,
  ShoppingBag,
  Upload,
  Users,
} from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { FaqSection, IntegrationsSection, PricingSection, QualitySection } from "@/components/marketing/sections";
import { Button } from "@/components/ui/button";
import { branding } from "@/lib/branding";

const STEPS = [
  { icon: Upload, title: "Upload your documents", body: "PDF, Word, Markdown and text files. Handbooks, policies, catalogs, manuals." },
  { icon: MessageSquareText, title: "Ask in plain language", body: "Staff or customers ask questions the way they would ask a colleague." },
  { icon: BadgeCheck, title: "Verify every answer", body: "Each answer cites the exact page and passage, one click away." },
];

const DIFFERENTIATORS = [
  {
    icon: BookOpenCheck,
    title: "Citations you can check",
    body: "Every claim links to the source passage. Citations are validated on the server, so an answer can only cite text that was actually retrieved.",
  },
  {
    icon: FileQuestion,
    title: "Honest when it does not know",
    body: "If your documents do not contain the answer, it says so instead of guessing, and logs the gap so you can fill it.",
  },
  {
    icon: LockKeyhole,
    title: "Your data stays yours",
    body: "Each workspace is isolated in the database itself, with row-level security behind every query.",
  },
];

const USE_CASES = [
  { icon: Users, title: "HR and onboarding", body: "New hires find leave, expense and conduct policies without waiting for a reply." },
  { icon: Headset, title: "Customer support", body: "Agents get cited answers from manuals and policies in seconds." },
  { icon: ShoppingBag, title: "E-commerce", body: "Shipping, returns and product questions answered from your own catalog." },
  { icon: GraduationCap, title: "Schools and training", body: "Learners query course handbooks and procedures directly." },
  { icon: Scale, title: "Legal and consultancy", body: "Search engagement documents and internal guidance with references." },
  { icon: Building2, title: "Operations teams", body: "Procedures and administrative policies in one searchable place." },
];

const SECURITY = [
  "Passwords hashed with Argon2id",
  "Sessions in httpOnly cookies with CSRF protection",
  "Workspace isolation enforced by Postgres row-level security",
  "Append-only audit log of sign-ins and sensitive actions",
];

export default function LandingPage() {
  return (
    <div className="bg-white">
      <header className="sticky top-0 z-30 border-b border-transparent bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link href="/" className="rounded-md">
            <Logo />
          </Link>
          <nav aria-label="Sections" className="hidden items-center gap-6 text-sm font-medium text-slate-subtle md:flex">
            <a href="#how" className="hover:text-navy-900">How it works</a>
            <a href="#use-cases" className="hover:text-navy-900">Use cases</a>
            <a href="#quality" className="hover:text-navy-900">Quality</a>
            <a href="#security" className="hover:text-navy-900">Security</a>
            <a href="#pricing" className="hover:text-navy-900">Pricing</a>
            <a href="#faq" className="hover:text-navy-900">FAQ</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Button asChild variant="ghost" size="lg">
              <Link href="/login">Sign in</Link>
            </Button>
            <Button asChild size="lg">
              <Link href="/register">Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      <main id="main">
        <section className="relative overflow-hidden bg-navy-900 text-white">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(20,184,166,0.25),transparent_40%),radial-gradient(circle_at_85%_70%,rgba(34,211,238,0.16),transparent_45%)]"
          />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28">
            <div className="grid gap-6">
              <p className="w-fit rounded-full border border-teal-500/40 bg-teal-500/10 px-3 py-1 text-xs font-medium text-teal-100">
                Knowledge base answers with sources
              </p>
              <h1 className="text-4xl leading-[1.1] font-semibold sm:text-5xl">{branding.tagline}</h1>
              <p className="max-w-xl text-lg text-navy-100">
                Upload your business documents. Your team and customers ask questions in plain language and get answers
                with clickable citations to the exact page. When the documents do not cover it, {branding.productName}{" "}
                says so.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild size="lg" className="h-11 bg-teal-500 px-5 text-navy-950 hover:bg-teal-500/90">
                  <Link href="/register">
                    Create a workspace <ArrowRight aria-hidden />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="h-11 border-white/25 bg-transparent px-5 text-white hover:bg-white/10 hover:text-white">
                  <a href="#how">See how it works</a>
                </Button>
              </div>
            </div>
            <HeroIllustration />
          </div>
        </section>

        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <SectionHeading eyebrow="How it works" title="From scattered files to answers you can trust" />
          <ol className="mt-12 grid gap-6 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="rounded-2xl border bg-white p-6 shadow-soft">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-xl bg-teal-50 text-teal-700">
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <span className="text-sm font-medium text-slate-subtle">Step {i + 1}</span>
                </div>
                <h3 className="mt-4 text-lg font-semibold text-navy-900">{title}</h3>
                <p className="mt-2 text-slate-body">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="bg-navy-50">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <SectionHeading eyebrow="Why it is different" title="Built for accuracy, not just a chat box" />
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {DIFFERENTIATORS.map(({ icon: Icon, title, body }) => (
                <div key={title} className="rounded-2xl bg-white p-6 shadow-soft">
                  <Icon className="size-6 text-teal-700" aria-hidden />
                  <h3 className="mt-4 text-lg font-semibold text-navy-900">{title}</h3>
                  <p className="mt-2 text-slate-body">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="use-cases" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <SectionHeading eyebrow="Use cases" title="Wherever answers live in documents" />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {USE_CASES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex gap-4 rounded-2xl border p-5">
                <Icon className="mt-0.5 size-5 shrink-0 text-teal-700" aria-hidden />
                <div>
                  <h3 className="font-semibold text-navy-900">{title}</h3>
                  <p className="mt-1 text-sm text-slate-body">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <QualitySection />

        <IntegrationsSection />

        <section id="security" className="scroll-mt-20 bg-navy-900 text-white">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2">
            <div className="grid content-start gap-4">
              <ShieldCheck className="size-8 text-teal-500" aria-hidden />
              <h2 className="text-3xl font-semibold">Security from the first line of code</h2>
              <p className="text-navy-100">
                Document text is treated as data, never as instructions. Every request is authorized on the server, and
                each workspace can only ever see its own documents.
              </p>
            </div>
            <ul className="grid content-start gap-3">
              {SECURITY.map((item) => (
                <li key={item} className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/5 p-4">
                  <BadgeCheck className="mt-0.5 size-5 shrink-0 text-teal-500" aria-hidden />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <PricingSection />

        <FaqSection />

        <section className="mx-auto max-w-6xl px-4 py-20 text-center sm:px-6">
          <h2 className="text-3xl font-semibold text-navy-900">Put your documents to work</h2>
          <p className="mx-auto mt-3 max-w-xl text-slate-body">Create a workspace in under a minute.</p>
          <Button asChild size="lg" className="mt-8 h-11 px-6">
            <Link href="/register">
              Get started <ArrowRight aria-hidden />
            </Link>
          </Button>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 text-sm text-slate-subtle sm:px-6 md:grid-cols-[1fr_auto]">
          <div className="grid gap-2">
            <Logo />
            <p>{branding.tagline}</p>
            <p className="text-xs">Example content on this page is fictional. Pricing is illustrative.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap content-start gap-x-6 gap-y-2">
            <a href="#how" className="hover:text-navy-900">How it works</a>
            <a href="#quality" className="hover:text-navy-900">Quality</a>
            <a href="#security" className="hover:text-navy-900">Security</a>
            <a href="#pricing" className="hover:text-navy-900">Pricing</a>
            <Link href="/login" className="hover:text-navy-900">Sign in</Link>
            <Link href="/register" className="hover:text-navy-900">Create a workspace</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-semibold tracking-wide text-teal-700 uppercase">{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-semibold text-navy-900 sm:text-4xl">{title}</h2>
    </div>
  );
}

/** Diagram of the product idea (not a screenshot; real screenshots come from the seeded demo). */
function HeroIllustration() {
  return (
    <figure className="relative">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-overlay backdrop-blur">
        <div className="rounded-xl bg-white p-5 text-navy-900">
          <p className="text-xs font-medium tracking-wide text-slate-subtle uppercase">Question</p>
          <p className="mt-1 font-medium">How many days of annual leave do new employees get?</p>
          <div className="mt-5 border-t pt-4">
            <p className="text-xs font-medium tracking-wide text-slate-subtle uppercase">Answer</p>
            <p className="mt-1 text-slate-body">
              New employees receive 20 days of annual leave per year, accrued monthly from their start date{" "}
              <CitationChip n={1} />. Unused days carry over up to a limit of 5 <CitationChip n={2} />.
            </p>
          </div>
          <div className="mt-5 grid gap-2">
            <SourceRow n={1} file="Employee Handbook.pdf" page={12} />
            <SourceRow n={2} file="Leave Policy.docx" page={3} />
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-navy-100/80">Illustration with fictional example content</figcaption>
    </figure>
  );
}

function CitationChip({ n }: { n: number }) {
  return (
    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-teal-50 px-1 align-text-top text-xs font-semibold text-teal-700 ring-1 ring-teal-100">
      {n}
    </span>
  );
}

function SourceRow({ n, file, page }: { n: number; file: string; page: number }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-navy-50/60 px-3 py-2 text-sm">
      <CitationChip n={n} />
      <FileText className="size-4 text-slate-subtle" aria-hidden />
      <span className="truncate font-medium">{file}</span>
      <span className="ml-auto shrink-0 text-slate-subtle">Page {page}</span>
    </div>
  );
}
