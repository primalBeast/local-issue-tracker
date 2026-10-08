import { describe, expect, it } from 'vitest';
import { bodyByteLength, createKeepaliveBudget, KEEPALIVE_BUDGET_BYTES } from './keepaliveBudget';

describe('keepalive budget', () => {
  it('counts UTF-8 bytes, including multibyte characters', () => {
    expect(bodyByteLength('a')).toBe(1);
    expect(bodyByteLength('é')).toBe(2);
    expect(bodyByteLength('😀')).toBe(4);
    expect(bodyByteLength('aé😀')).toBe(1 + 2 + 4);
    expect('😀'.length).toBe(2);
  });

  it('shares one budget across reservations and releases it on settle', () => {
    const budget = createKeepaliveBudget(10);
    const first = budget.tryReserve(bodyByteLength('éééé'));
    expect(first).not.toBeNull();
    expect(budget.used()).toBe(8);

    // 8 bytes in flight: another 2-byte character fits, 3 bytes do not.
    expect(budget.tryReserve(3)).toBeNull();
    const extra = budget.tryReserve(bodyByteLength('é'));
    expect(extra).not.toBeNull();
    expect(budget.used()).toBe(10);
    expect(budget.tryReserve(1)).toBeNull();
    extra!();
    expect(budget.used()).toBe(8);

    first!();
    expect(budget.used()).toBe(0);
    first!();
    expect(budget.used()).toBe(0);

    const second = budget.tryReserve(4);
    expect(second).not.toBeNull();
    expect(budget.used()).toBe(4);
    const third = budget.tryReserve(6);
    expect(third).not.toBeNull();
    expect(budget.used()).toBe(10);
    expect(budget.tryReserve(1)).toBeNull();
    second!();
    third!();
    expect(budget.used()).toBe(0);
  });

  it('rejects a single body larger than the cap even when nothing else is in flight', () => {
    const budget = createKeepaliveBudget(KEEPALIVE_BUDGET_BYTES);
    const full = budget.tryReserve(KEEPALIVE_BUDGET_BYTES);
    expect(full).not.toBeNull();
    expect(budget.used()).toBe(KEEPALIVE_BUDGET_BYTES);
    expect(budget.tryReserve(1)).toBeNull();
    full!();
    expect(budget.used()).toBe(0);

    const fresh = createKeepaliveBudget(KEEPALIVE_BUDGET_BYTES);
    expect(fresh.tryReserve(KEEPALIVE_BUDGET_BYTES + 1)).toBeNull();
    expect(fresh.used()).toBe(0);
    expect(fresh.tryReserve(1)).not.toBeNull();
  });
});
