import { describe, expect, it } from 'vitest';
import { formatMetric } from './format';

describe('formatMetric', () => {
  it('formats a reading with fixed decimals and a suffix', () => {
    expect(formatMetric(76.456, 1, '%')).toBe('76.5%');
    expect(formatMetric(61, 0, '°C')).toBe('61°C');
  });

  it('shows a dash when the reading is unavailable', () => {
    expect(formatMetric(null, 1, '%')).toBe('—');
    expect(formatMetric(undefined, 1, '%')).toBe('—');
    expect(formatMetric(Number.NaN, 1, '%')).toBe('—');
  });
});
