import { describe, expect, it } from 'vitest';
import { launchableHref, ticketHref } from './ticketUrl';

describe('ticketHref', () => {
  it('returns null when the prefix or ticket key is empty', () => {
    expect(ticketHref('', 'SHOP-1')).toBeNull();
    expect(ticketHref('   ', 'SHOP-1')).toBeNull();
    expect(ticketHref('https://jira.example/browse/', '')).toBeNull();
    expect(ticketHref(null, 'SHOP-1')).toBeNull();
  });

  it('concatenates a valid http(s) prefix and ticket key', () => {
    expect(ticketHref('https://jira.example/browse/', 'SHOP-12')).toBe(
      'https://jira.example/browse/SHOP-12'
    );
    expect(ticketHref('http://bugs.local/t=', 'ABC-1')).toBe('http://bugs.local/t=ABC-1');
  });

  it('rejects malformed or non-http prefixes', () => {
    expect(ticketHref('jira.example/browse/', 'SHOP-1')).toBeNull();
    expect(ticketHref('javascript:alert(1)//', 'SHOP-1')).toBeNull();
    expect(ticketHref('ftp://files.example/', 'SHOP-1')).toBeNull();
    expect(ticketHref('https://', 'SHOP-1')).toBeNull();
    expect(ticketHref('not a url', 'SHOP-1')).toBeNull();
  });
});

describe('launchableHref', () => {
  it('accepts a full http(s) URL and rejects junk', () => {
    expect(launchableHref('https://jira.example/browse/SHOP-1')).toBe(
      'https://jira.example/browse/SHOP-1'
    );
    expect(launchableHref('')).toBeNull();
    expect(launchableHref('jira.example/SHOP-1')).toBeNull();
    expect(launchableHref('javascript:alert(1)')).toBeNull();
  });
});
