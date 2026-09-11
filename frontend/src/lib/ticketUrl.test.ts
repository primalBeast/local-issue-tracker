import { describe, expect, it } from 'vitest';
import { launchableHref, splitTicketViewHtml, ticketHref } from './ticketUrl';

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

describe('splitTicketViewHtml', () => {
  it('puts the master ticket on the left and the external ticket on the right', () => {
    const html = splitTicketViewHtml(
      'https://jira.example/browse/SHOP-1',
      'https://ext.example/PS-9'
    );
    expect(html).toContain('Master ticket');
    expect(html).toContain('External ticket');
    expect(html).toContain('https://jira.example/browse/SHOP-1');
    expect(html).toContain('https://ext.example/PS-9');
    expect(html.indexOf('SHOP-1')).toBeLessThan(html!.indexOf('PS-9'));
  });

  it('still builds a page when the master URL is missing', () => {
    const html = splitTicketViewHtml(null, 'https://ext.example/PS-9');
    expect(html).toContain('https://ext.example/PS-9');
    expect(html).toContain('No URL for this side');
  });

  it('returns null without a valid external URL', () => {
    expect(splitTicketViewHtml('https://jira.example/browse/A-1', 'not-a-url')).toBeNull();
    expect(splitTicketViewHtml('https://jira.example/browse/A-1', 'javascript:alert(1)')).toBeNull();
  });
});
