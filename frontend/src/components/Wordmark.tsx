/**
 * The mark.
 *
 * Not a shield. A shield is the default badge for anything security-adjacent and
 * says nothing about this particular product.
 *
 * A chargeback is a *reversal* — settled money travelling back up the rails — and
 * this system's job is to stop it at a decision point. So the mark is a rule with
 * a return arrow turning back against it, drawn at hairline weight like a
 * printer's ornament rather than an app icon. It reads as a ledger rule with a
 * correction, which is exactly what a representment is.
 */
export function Mark({ className = 'w-6 h-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden focusable="false">
      {/* the settlement rule */}
      <path d="M2 17.5h20" stroke="currentColor" strokeWidth="1.25" strokeLinecap="square" />
      {/* the reversal, turning back on itself */}
      <path
        d="M19 11.5H8.5a3.5 3.5 0 0 1 0-7H16"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="square"
      />
      <path d="M12.5 1.5 16 4.5 12.5 7.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="square" strokeLinejoin="miter" />
      {/* the decision point on the rule */}
      <rect x="17.5" y="15.5" width="4" height="4" fill="currentColor" />
    </svg>
  );
}

export function Wordmark({
  className = '',
  sub,
}: {
  className?: string;
  sub?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Mark className="w-[1.15em] h-[1.15em] shrink-0" />
      <span className="font-display font-medium tracking-[.14em] leading-none">RAKSHAK</span>
      {sub && (
        <>
          <span className="w-px h-4 bg-current opacity-25" aria-hidden />
          <span className="font-mono text-[.62em] tracking-[.12em] uppercase opacity-60 leading-none">
            {sub}
          </span>
        </>
      )}
    </span>
  );
}
