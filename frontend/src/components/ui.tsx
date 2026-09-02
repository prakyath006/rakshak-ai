import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

/* --------------------------------------------------------------------------
 * Primitives for the working document.
 *
 * The application is set in the same language as the site: paper, hairline
 * rules, tabular figures, a serif for headings. There are no rounded cards, no
 * shadows and no gradients — structure comes from ruling, the way it does in a
 * printed report. A working tool is denser than a marketing page, so the type
 * is smaller and the tables tighter, but the vocabulary is the same.
 * ------------------------------------------------------------------------ */

export function Panel({
  children,
  className = '',
  raised = true,
}: {
  children: ReactNode;
  className?: string;
  raised?: boolean;
}) {
  return (
    <section
      className={`${raised ? 'bg-paper-raised' : 'bg-paper'} border border-paper-rule ${className}`}
    >
      {children}
    </section>
  );
}

/** Section head: a serif title over a hairline, optionally with a note. */
export function Head({
  children,
  note,
  right,
  n,
}: {
  children: ReactNode;
  note?: ReactNode;
  right?: ReactNode;
  n?: string;
}) {
  return (
    <div className="mb-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-display text-[1.15rem] leading-tight tracking-[-.01em] text-graphite-900 flex items-baseline gap-2.5">
            {n && <span className="fig text-graphite-400 text-xs shrink-0">{n}</span>}
            {children}
          </h3>
          {note && <p className="note mt-2 leading-relaxed max-w-[46rem]">{note}</p>}
        </div>
        {right}
      </div>
    </div>
  );
}

/** A figure with its label, set as a statement rather than a card. */
export function Stat({
  label,
  value,
  sub,
  tone = 'default',
  accent = false,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: 'default' | 'gain' | 'loss' | 'press';
  /** Marks the lead figure — a heavy rule above it, the way a report does. */
  accent?: boolean;
}) {
  const color = {
    default: 'text-graphite-900',
    gain: 'text-gain',
    loss: 'text-loss',
    press: 'text-press',
  }[tone];
  return (
    <div className={`bg-paper-raised px-5 py-5 ${accent ? 'border-t-2 border-graphite-900' : ''}`}>
      <div className="smallcaps text-graphite-500 text-[.7rem] mb-2.5">{label}</div>
      <div className={`fig text-[1.75rem] leading-none ${color}`}>{value}</div>
      {sub && <div className="note mt-2.5 leading-snug">{sub}</div>}
    </div>
  );
}

/** Counts a figure up on mount. Reduced-motion settles instantly. */
export function CountUp({
  value,
  format,
  duration = 900,
}: {
  value: number;
  format: (n: number) => string;
  duration?: number;
}) {
  const [shown, setShown] = useState(value);
  const first = useRef(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(value);
      return;
    }
    const from = first.current ? 0 : shown;
    first.current = false;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(from + (value - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  return <>{format(shown)}</>;
}

/** Status chip. Reserved colours only, always with a word — never hue alone. */
export function Tag({
  children,
  tone = 'neutral',
  title,
  className = '',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'gain' | 'loss' | 'press' | 'warn';
  title?: string;
  className?: string;
}) {
  const styles = {
    neutral: 'border-paper-rule text-graphite-500 bg-paper',
    gain: 'border-gain/35 text-gain bg-gain/[.06]',
    loss: 'border-loss/35 text-loss bg-loss/[.06]',
    press: 'border-press/35 text-press bg-press/[.06]',
    warn: 'border-warn/50 text-[#8a6110] bg-warn/[.1]',
  }[tone];
  return (
    <span
      title={title}
      className={`font-mono text-[.65rem] tracking-[.06em] uppercase px-2 py-[3px] border inline-flex items-center gap-1.5 whitespace-nowrap ${styles} ${className}`}
    >
      {children}
    </span>
  );
}

export function Rule({ heavy = false, soft = false }: { heavy?: boolean; soft?: boolean }) {
  return <div className={heavy ? 'hr-heavy' : soft ? 'hr-soft' : 'hr'} />;
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`shimmer-paper ${className}`} />;
}

export function ChartSkeleton() {
  return (
    <Panel className="p-5">
      <Skeleton className="h-4 w-52 mb-3" />
      <Skeleton className="h-3 w-80 mb-6" />
      <Skeleton className="h-56 w-full" />
    </Panel>
  );
}

/* --------------------------------------------------------------------------
 * Compatibility aliases.
 *
 * `Card` and `PanelTitle` are the previous dark-dashboard names, still used by
 * the dispute workspace. They now render the paper treatment, so nothing looks
 * out of place during the migration; the names go away when those panels are
 * rewritten.
 * ------------------------------------------------------------------------ */
export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  as?: 'div' | 'section';
}) {
  return <div className={`bg-paper-raised border border-paper-rule ${className}`}>{children}</div>;
}

export function PanelTitle({
  icon,
  children,
  right,
  sub,
}: {
  icon?: ReactNode;
  children: ReactNode;
  right?: ReactNode;
  sub?: string;
}) {
  return <Head right={right} note={sub}>{icon}{children}</Head>;
}

export const Badge = Tag;
