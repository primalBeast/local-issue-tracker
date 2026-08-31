import { describe, expect, it } from 'vitest';
import { findNoteDateAround, formatNoteDate, formatNoteDateStamp } from './noteDate';

describe('formatNoteDateStamp', () => {
  it('formats month/day without padding', () => {
    expect(formatNoteDate(new Date(2026, 0, 5))).toBe('1/5');
    expect(formatNoteDateStamp(new Date(2026, 0, 5))).toBe('1/5 - ');
    expect(formatNoteDateStamp(new Date(2026, 7, 17))).toBe('8/17 - ');
    expect(formatNoteDateStamp(new Date(2026, 11, 31))).toBe('12/31 - ');
  });
});

describe('findNoteDateAround', () => {
  const text = 'hello 8/17 - more';
  //           0123456789
  //                 ^ 8 at 6, / 7, 1 8, 7 9, space 10

  it('hits a date when the caret is inside it or just after the last digit', () => {
    expect(findNoteDateAround(text, 6)).toEqual({ start: 6, end: 10 });
    expect(findNoteDateAround(text, 7)).toEqual({ start: 6, end: 10 });
    expect(findNoteDateAround(text, 9)).toEqual({ start: 6, end: 10 });
    expect(findNoteDateAround(text, 10)).toEqual({ start: 6, end: 10 });
  });

  it('misses when the caret is in the following " - " or other text', () => {
    expect(findNoteDateAround(text, 0)).toBeNull();
    expect(findNoteDateAround(text, 5)).toBeNull();
    expect(findNoteDateAround(text, 11)).toBeNull();
    expect(findNoteDateAround(text, 12)).toBeNull();
  });

  it('accepts zero-padded mm/dd and ignores year-style dates', () => {
    expect(findNoteDateAround('on 08/17 done', 6)).toEqual({ start: 3, end: 8 });
    expect(findNoteDateAround('8/17/2026', 2)).toBeNull();
    expect(findNoteDateAround('13/1 x', 2)).toBeNull();
  });
});
