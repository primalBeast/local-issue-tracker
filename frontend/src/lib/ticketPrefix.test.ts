import { describe, expect, it } from 'vitest';
import { nextTicketKey, normalizeTicketPrefix, slugFromName, uniqueSlug } from './ticketPrefix';

describe('ticketPrefix', () => {
  it('normalizes a prefix and adds a trailing hyphen', () => {
    expect(normalizeTicketPrefix('NEW-')).toBe('NEW-');
    expect(normalizeTicketPrefix('lit')).toBe('lit-');
    expect(normalizeTicketPrefix('  ABC_  ')).toBe('ABC_');
    expect(normalizeTicketPrefix('')).toBe('NEW-');
  });

  it('picks the next number for the current prefix', () => {
    expect(nextTicketKey([], 'NEW-')).toBe('NEW-1');
    expect(nextTicketKey(['NEW-1', 'NEW-3', 'OTHER-9'], 'NEW-')).toBe('NEW-4');
    expect(nextTicketKey(['LIT-2'], 'LIT')).toBe('LIT-3');
  });

  it('builds a unique slug from a display name', () => {
    expect(slugFromName('My Work')).toBe('my-work');
    expect(uniqueSlug('my-work', ['my-work'])).toBe('my-work-2');
    expect(uniqueSlug('ok', [])).toBe('ok');
  });
});
