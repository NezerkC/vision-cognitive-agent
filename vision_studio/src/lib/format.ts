/** A hardware reading for display, or a dash when the gateway reported none (no GPU, no sensor, not connected). */
export function formatMetric(value: number | null | undefined, digits = 1, suffix = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)}${suffix}`;
}
