import { describe, expect, it } from 'vitest';
import { formatDuration, liveSeconds } from './waiting';

describe('waiting', () => {
  it('formats durations', () => {
    expect(formatDuration(45)).toBe('45s');
    expect(formatDuration(125)).toBe('2m 5s');
    expect(formatDuration(3700)).toBe('1h 1m');
  });

  it('computes live seconds', () => {
    const start = new Date(Date.UTC(2026, 0, 1, 0, 0, 0)).toISOString();
    const now = Date.UTC(2026, 0, 1, 0, 1, 30);
    expect(liveSeconds(start, now)).toBe(90);
  });
});
