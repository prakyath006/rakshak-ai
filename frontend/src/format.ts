/** Display helpers. Indian numbering throughout, since the money is in rupees. */

export function inr(value: number, decimals = 0): string {
  return `₹${value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/** Indian short scale: 1,94,900 -> ₹1.95L, 10,690,903 -> ₹10.69Cr */
export function inrCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)}L`;
  if (abs >= 1e3) return `₹${(value / 1e3).toFixed(1)}K`;
  return `₹${value.toFixed(0)}`;
}

export function pct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function bps(value: number, decimals = 0): string {
  return `${value.toFixed(decimals)} bps`;
}

export function count(value: number): string {
  return value.toLocaleString('en-IN');
}

export const ACTION_TONE: Record<string, { text: string; bg: string; dot: string }> = {
  APPROVE: { text: 'text-[#5cc79f]', bg: 'bg-[#199e70]/12 border-[#199e70]/35', dot: 'bg-[#199e70]' },
  STEP_UP: { text: 'text-signal-300', bg: 'bg-signal-500/12 border-signal-500/35', dot: 'bg-signal-500' },
  REVIEW: { text: 'text-warn', bg: 'bg-warn/12 border-warn/35', dot: 'bg-warn' },
  BLOCK: { text: 'text-critical', bg: 'bg-critical/12 border-critical/35', dot: 'bg-critical' },
};
