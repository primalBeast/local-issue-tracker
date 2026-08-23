import { describe, expect, it } from 'vitest';
import { formatDuration, formatWaitingDays, isItemWaiting, liveSeconds, todayLocalDate } from './waiting';

describe('waiting', () => {
  it('formats durations', () => {
    expect(formatDuration(45)).toBe('45s');
    expect(formatDuration(125)).toBe('2m 5s');
    expect(formatDuration(3700)).toBe('1h 1m');
  });

  it('formats waiting as whole days only', () => {
    expect(formatWaitingDays(3600)).toBe('0 days');
    expect(formatWaitingDays(86400)).toBe('1 day');
    expect(formatWaitingDays(86400 * 3 + 100)).toBe('3 days');
  });

  it('treats the waiting checkbox or an open period as waiting', () => {
    expect(isItemWaiting({ fields: { waiting: true } })).toBe(true);
    expect(isItemWaiting({ fields: { waiting: false }, waiting: { is_waiting: true } })).toBe(true);
    expect(isItemWaiting({ fields: { waiting: false, waiting_for: 'Pat' } })).toBe(false);
  });

  it('formats a local calendar date', () => {
    expect(todayLocalDate(new Date(2026, 7, 20, 15, 30, 0))).toBe('2026-08-20');
  });

  it('computes live seconds', () => {
    const start = new Date(Date.UTC(2026, 0, 1, 0, 0, 0)).toISOString();
    const now = Date.UTC(2026, 0, 1, 0, 1, 30);
    expect(liveSeconds(start, now)).toBe(90);
  });
});
