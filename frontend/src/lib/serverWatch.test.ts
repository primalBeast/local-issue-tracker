import { describe, expect, it } from 'vitest';
import { shouldAutoRestart } from './serverWatch';

describe('shouldAutoRestart', () => {
  it('waits out a short blip', () => {
    expect(shouldAutoRestart(1_000, 1_000 + 14_999, false)).toBe(false);
  });

  it('restarts after the server has been quiet for 15 seconds', () => {
    expect(shouldAutoRestart(1_000, 16_000, false)).toBe(true);
  });

  it('does not stack a second restart', () => {
    expect(shouldAutoRestart(1_000, 20_000, true)).toBe(false);
    expect(shouldAutoRestart(0, 20_000, false)).toBe(false);
  });
});
