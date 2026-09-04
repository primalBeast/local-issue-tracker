import { describe, expect, it } from 'vitest';
import { calendarMonth, formatIsoDate, parseIsoDate } from './listCalendar';

describe('parseIsoDate', () => {
  it('parses a local calendar date and rejects junk', () => {
    const d = parseIsoDate('2026-08-20');
    expect(d).toBeInstanceOf(Date);
    expect(d?.getFullYear()).toBe(2026);
    expect(d?.getMonth()).toBe(7);
    expect(d?.getDate()).toBe(20);
    expect(parseIsoDate('')).toBeNull();
    expect(parseIsoDate('2026-13-01')).toBeNull();
    expect(parseIsoDate('2026-02-30')).toBeNull();
  });
});

describe('calendarMonth', () => {
  it('fills a 6×7 grid starting on Sunday', () => {
    // 1 Aug 2026 is a Saturday, so the grid starts on 26 Jul.
    const cells = calendarMonth(2026, 7);
    expect(cells).toHaveLength(42);
    expect(cells[0]).toEqual({ iso: '2026-07-26', day: 26, inMonth: false });
    expect(cells[6]).toEqual({ iso: '2026-08-01', day: 1, inMonth: true });
    expect(cells[36]).toEqual({ iso: '2026-08-31', day: 31, inMonth: true });
    expect(cells[37]).toEqual({ iso: '2026-09-01', day: 1, inMonth: false });
  });
});

describe('formatIsoDate', () => {
  it('pads month and day', () => {
    expect(formatIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05');
  });
});
