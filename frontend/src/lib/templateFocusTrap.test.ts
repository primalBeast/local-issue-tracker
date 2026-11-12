import { describe, expect, it } from 'vitest';
import { FOCUSABLE_SELECTOR, wrapFocusIndex } from './templateFocusTrap';

describe('focus trap', () => {
  it('wraps Tab from the last control to the first, and Shift+Tab the other way', () => {
    expect(wrapFocusIndex(4, 3, false)).toBe(0);
    expect(wrapFocusIndex(4, 0, true)).toBe(3);
    expect(wrapFocusIndex(4, 1, false)).toBe(2);
    expect(wrapFocusIndex(4, 1, true)).toBe(0);
    expect(FOCUSABLE_SELECTOR).toContain('button:not([disabled])');
  });
});
