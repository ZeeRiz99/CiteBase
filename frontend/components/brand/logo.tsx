import { cn } from "@/lib/utils";
import { branding } from "@/lib/branding";

/** Mark: a document with a verified badge, for "answers you can verify". */
export function LogoMark({ className, title }: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("size-8 shrink-0", className)}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <rect width="32" height="32" rx="8" fill="#0B1B33" />
      <path d="M10 6.5h8.2l5.3 5.3V25a1.5 1.5 0 0 1-1.5 1.5H10A1.5 1.5 0 0 1 8.5 25V8A1.5 1.5 0 0 1 10 6.5Z" fill="#F3F6FB" />
      <path d="M18.2 6.5v3.8a1.5 1.5 0 0 0 1.5 1.5h3.8" fill="#C9D4E5" />
      <path d="M11.8 15.5h7.4M11.8 18.8h4.8" stroke="#526178" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="22.5" cy="22.5" r="5.25" fill="#14B8A6" stroke="#0B1B33" strokeWidth="1.5" />
      <path d="m20.3 22.6 1.5 1.5 2.9-3" fill="none" stroke="#061128" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className={cn("text-lg font-semibold tracking-tight", inverted ? "text-white" : "text-navy-900")}>
        {branding.productName}
      </span>
    </span>
  );
}
