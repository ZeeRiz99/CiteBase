import { Check, ChevronDown, Clock, FileText, KeyRound, Plug, Server } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { branding } from "@/lib/branding";

/* Numbers come only from the evaluation harness report (docs/evals/2026-11-17-baseline.md). */
const QUALITY = [
  { value: "100%", label: "Citation precision", note: "cited passages that contain the expected fact" },
  { value: "100%", label: "Refusal accuracy", note: "answered when it should, refused when it should" },
  { value: "100%", label: "Prompt-injection resistance", note: "planted instructions in a document were ignored" },
  { value: "2.0 s", label: "Median answer time", note: "full answer, Gemini Flash-Lite free tier" },
];

export function QualitySection() {
  return (
    <section id="quality" className="scroll-mt-20 bg-navy-50">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-teal-700 uppercase">Measured, not promised</p>
          <h2 className="mt-2 text-3xl font-semibold text-navy-900 sm:text-4xl">Quality you can test</h2>
          <p className="mt-3 text-slate-body">
            It ships with an evaluation harness that scores answers on answerable questions, off-topic questions, near misses and
            documents that try to inject instructions.
          </p>
        </div>
        <dl className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {QUALITY.map((q) => (
            <div key={q.label} className="rounded-2xl bg-white p-6 shadow-soft">
              <dt className="text-sm font-medium text-slate-subtle">{q.label}</dt>
              <dd className="mt-1 text-4xl font-semibold text-navy-900">{q.value}</dd>
              <dd className="mt-2 text-sm text-slate-body">{q.note}</dd>
            </div>
          ))}
        </dl>
        <p className="mx-auto mt-6 max-w-3xl text-center text-sm text-slate-subtle">
          Measured on a fictional 6-document demo corpus with 40 questions (answer quality judged by a model, so
          approximate). It is a small set: treat it as a smoke test. The same harness can be run on your own documents.
        </p>
      </div>
    </section>
  );
}

const AVAILABLE = [
  { icon: FileText, title: "PDF, Word, Markdown, text", body: "Tables and headings are kept. Scanned PDFs are detected and flagged rather than indexed empty." },
  { icon: KeyRound, title: "Your choice of AI provider", body: "Gemini by default; OpenAI and Anthropic adapters are included. Keys stay on the server." },
  { icon: Server, title: "Self-hosted with Docker", body: "One deployment per organization, your own domain and branding, an optional local embedding model." },
];

const PLANNED = ["Website chat widget", "Google Drive and folder sync", "Webhooks and n8n workflows", "Teams and document permissions"];

export function IntegrationsSection() {
  return (
    <section id="integrations" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold tracking-wide text-teal-700 uppercase">Integrations</p>
        <h2 className="mt-2 text-3xl font-semibold text-navy-900 sm:text-4xl">Works with what you have</h2>
      </div>
      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {AVAILABLE.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border p-6">
            <Icon className="size-6 text-teal-700" aria-hidden />
            <h3 className="mt-4 font-semibold text-navy-900">{title}</h3>
            <p className="mt-2 text-sm text-slate-body">{body}</p>
          </div>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <span className="flex items-center gap-1.5 text-sm font-medium text-slate-subtle">
          <Plug className="size-4" aria-hidden /> Planned:
        </span>
        {PLANNED.map((item) => (
          <span key={item} className="flex items-center gap-1.5 rounded-full border border-dashed px-3 py-1 text-sm text-slate-subtle">
            <Clock className="size-3.5" aria-hidden /> {item}
          </span>
        ))}
      </div>
    </section>
  );
}

/* Illustrative plans. "Included" lists only features that exist today; "planned" ones are labeled.
   Plan limits are not enforced yet (docs/BACKLOG.md: plan limits and billing). */
type Plan = {
  name: string;
  price: string;
  audience: string;
  limits: [string, string][];
  intro?: string;
  features: string[];
  planned: string[];
  cta: string;
  featured?: boolean;
};

const PLANS: Plan[] = [
  {
    name: "Free",
    price: "$0",
    audience: "Try it on your own documents",
    limits: [["Pages", "50"], ["Questions / month", "50"], ["Seats", "1"]],
    features: [
      "PDF, Word, Markdown and text",
      "Cited answers with the passage highlighted",
      'A clear "not in your documents" answer',
    ],
    planned: [],
    cta: "Start free",
  },
  {
    name: "Starter",
    price: "$29",
    audience: "Small businesses and internal teams",
    limits: [["Pages", "1,000"], ["Questions / month", "2,000"], ["Seats", "3"]],
    intro: "Everything in Free, plus",
    features: ["Unanswered-questions log", "Answer ratings with comments", "Team invites with admin, member and viewer roles"],
    planned: ["Website chat widget"],
    cta: "Get started",
  },
  {
    name: "Growth",
    price: "$79",
    audience: "Growing companies and support desks",
    limits: [["Pages", "5,000"], ["Questions / month", "10,000"], ["Seats", "10"]],
    intro: "Everything in Starter, plus",
    features: ['"Why this answer?" traces', "Usage dashboard", "Suggested questions from your documents"],
    planned: ["OCR for scanned PDFs", "Q&A export"],
    cta: "Get started",
    featured: true,
  },
  {
    name: "Business",
    price: "$199",
    audience: "Larger teams and agencies",
    limits: [["Pages", "25,000"], ["Questions / month", "35,000"], ["Seats", "25"]],
    intro: "Everything in Growth, plus",
    features: [
      "Your domain and branding",
      "Your own AI provider keys",
      "Quality evaluation on your documents",
      "Priority support",
    ],
    planned: ["API and webhooks"],
    cta: "Talk to us",
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className="scroll-mt-20 bg-navy-50">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-teal-700 uppercase">Pricing</p>
          <h2 className="mt-2 text-3xl font-semibold text-navy-900 sm:text-4xl">Simple plans</h2>
          <p className="mt-3">
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900">
              Illustrative pricing, not a binding offer
            </span>
          </p>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {PLANS.map((plan) => {
            const dark = plan.featured === true;
            return (
              <div
                key={plan.name}
                className={
                  dark
                    ? "flex flex-col gap-5 rounded-2xl bg-navy-900 p-6 text-white shadow-overlay"
                    : "flex flex-col gap-5 rounded-2xl bg-white p-6 shadow-soft"
                }
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h3 className={dark ? "font-semibold text-teal-100" : "font-semibold text-navy-900"}>{plan.name}</h3>
                    {dark ? (
                      <span className="rounded-full bg-teal-500 px-2.5 py-0.5 text-xs font-semibold text-navy-950">Recommended</span>
                    ) : null}
                  </div>
                  <p className="mt-2">
                    <span className="text-4xl font-semibold">{plan.price}</span>{" "}
                    <span className={dark ? "text-navy-100" : "text-slate-subtle"}>per month</span>
                  </p>
                  <p className={dark ? "mt-1 text-sm text-navy-100 lg:min-h-10" : "mt-1 text-sm text-slate-subtle lg:min-h-10"}>
                    {plan.audience}
                  </p>
                </div>
                <dl className={dark ? "grid gap-1.5 border-y border-white/15 py-4 text-sm" : "grid gap-1.5 border-y py-4 text-sm"}>
                  {plan.limits.map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-2">
                      <dt className={dark ? "text-navy-100" : "text-slate-subtle"}>{label}</dt>
                      <dd className="font-semibold">{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="grid content-start gap-2 text-sm">
                  {plan.intro ? <p className={dark ? "font-medium text-teal-100" : "font-medium text-navy-900"}>{plan.intro}</p> : null}
                  <ul className="grid gap-2">
                    {plan.features.map((f) => (
                      <li key={f} className="flex gap-2">
                        <Check className={dark ? "mt-0.5 size-4 shrink-0 text-teal-500" : "mt-0.5 size-4 shrink-0 text-teal-700"} aria-hidden />
                        {f}
                      </li>
                    ))}
                    {plan.planned.map((f) => (
                      <li key={f} className={dark ? "flex gap-2 text-navy-100" : "flex gap-2 text-slate-subtle"}>
                        <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
                        <span>
                          {f} <span className="text-xs font-medium">(planned)</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  asChild
                  size="lg"
                  variant={dark ? "default" : "outline"}
                  className={dark ? "mt-auto h-10 bg-teal-500 text-navy-950 hover:bg-teal-500/90" : "mt-auto h-10"}
                >
                  <Link href="/register">{plan.cta}</Link>
                </Button>
              </div>
            );
          })}
        </div>
        <p className="mt-8 text-center text-sm text-slate-body">
          <Server className="mr-1.5 inline size-4 align-text-bottom text-teal-700" aria-hidden />
          Need it on your own server? We can install a private copy for your team.
        </p>
      </div>
    </section>
  );
}

const FAQ = [
  {
    q: "Does it make things up?",
    a: `${branding.productName} answers only from passages it retrieves from your documents, and every claim cites one. Citations are checked on the server; an answer without a valid citation is regenerated once and otherwise withheld. When nothing relevant is found, the AI model is not called at all and you get a clear "couldn't find it" instead.`,
  },
  {
    q: "Which files can I upload?",
    a: "PDF, Word (.docx), Markdown and plain text, up to 25 MB each by default. Scanned PDFs without a text layer are detected and marked \"Needs OCR\"; text recognition for them is not included yet.",
  },
  {
    q: "Where are my documents stored?",
    a: "On the server you deploy, in your own database and storage. Each workspace is isolated by row-level security in the database. Passages relevant to a question are sent to the AI provider you configure to write the answer.",
  },
  {
    q: "Which AI models does it use?",
    a: "Gemini by default, with adapters for OpenAI and Anthropic. Embeddings can run on a local model instead of an API. Model names are configuration, not code.",
  },
  {
    q: "What happens to questions it cannot answer?",
    a: "They are logged in an Unanswered list for admins, with the reason. Each one points to a gap in your documents you can fill.",
  },
  {
    q: "Can we use our own name and colors?",
    a: "Yes. The product name, tagline and design tokens come from configuration, so each deployment can carry your brand.",
  },
];

export function FaqSection() {
  return (
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-4 py-20 sm:px-6">
      <div className="text-center">
        <p className="text-sm font-semibold tracking-wide text-teal-700 uppercase">FAQ</p>
        <h2 className="mt-2 text-3xl font-semibold text-navy-900 sm:text-4xl">Questions, answered</h2>
      </div>
      <div className="mt-10 grid gap-3">
        {FAQ.map(({ q, a }) => (
          <details key={q} className="group rounded-xl border bg-white px-5 py-4 open:shadow-soft">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-navy-900 [&::-webkit-details-marker]:hidden">
              {q}
              <ChevronDown className="size-4 shrink-0 text-slate-subtle transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <p className="mt-3 text-slate-body">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
