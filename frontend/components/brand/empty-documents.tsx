/** Empty-state illustration: stacked documents with a citation badge. Hand-authored SVG. */
export function EmptyDocumentsIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" className={className} aria-hidden fill="none">
      <rect x="18" y="96" width="124" height="8" rx="4" fill="#E4EBF5" />
      <rect x="44" y="18" width="62" height="78" rx="8" fill="#E4EBF5" transform="rotate(-8 44 18)" />
      <rect x="54" y="14" width="62" height="80" rx="8" fill="#FFFFFF" stroke="#C9D4E5" strokeWidth="2" />
      <path d="M66 32h38M66 42h38M66 52h26" stroke="#C9D4E5" strokeWidth="4" strokeLinecap="round" />
      <path d="M66 64h30" stroke="#14B8A6" strokeWidth="4" strokeLinecap="round" />
      <circle cx="112" cy="80" r="16" fill="#0F766E" />
      <path d="m105 80 5 5 9-10" stroke="#FFFFFF" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="40" cy="30" r="4" fill="#22D3EE" opacity=".5" />
      <circle cx="132" cy="36" r="3" fill="#14B8A6" opacity=".5" />
    </svg>
  );
}
