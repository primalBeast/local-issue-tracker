import { describe, expect, it } from 'vitest';
import { wokeFromSleep } from './wake';

describe('wokeFromSleep', () => {
  it('ignores a normal health-check gap', () => {
    expect(wokeFromSleep(1_000, 5_000)).toBe(false);
  });

  it('notices a sleep-sized jump', () => {
    expect(wokeFromSleep(1_000, 1_000 + 60_000)).toBe(true);
  });

  it('ignores a clock that moved backwards', () => {
    expect(wokeFromSleep(5_000, 1_000)).toBe(false);
  });
});
