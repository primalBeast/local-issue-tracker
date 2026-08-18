import { describe, expect, it } from 'vitest';
import { formatNoteDateStamp } from './noteDate';

describe('formatNoteDateStamp', () => {
  it('formats month/day without padding', () => {
    expect(formatNoteDateStamp(new Date(2026, 0, 5))).toBe('1/5 - ');
    expect(formatNoteDateStamp(new Date(2026, 7, 17))).toBe('8/17 - ');
    expect(formatNoteDateStamp(new Date(2026, 11, 31))).toBe('12/31 - ');
  });
});
