import { describe, expect, it } from 'vitest';
import { launchableHref, splitTicketUrls, ticketHref, ticketNumberLabel } from './ticketUrl';

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

  it('uses a full ticket URL as-is and ignores the prefix', () => {
    expect(
      ticketHref('https://jira.example/browse/', 'https://other.example/browse/EXT-9')
    ).toBe('https://other.example/browse/EXT-9');
    expect(ticketHref('', 'https://jira.example/browse/SHOP-1')).toBe(
      'https://jira.example/browse/SHOP-1'
    );
  });

  it('rejects malformed or non-http prefixes', () => {
    expect(ticketHref('jira.example/browse/', 'SHOP-1')).toBeNull();
    expect(ticketHref('javascript:alert(1)//', 'SHOP-1')).toBeNull();
    expect(ticketHref('ftp://files.example/', 'SHOP-1')).toBeNull();
    expect(ticketHref('https://', 'SHOP-1')).toBeNull();
    expect(ticketHref('not a url', 'SHOP-1')).toBeNull();
  });
});

describe('ticketNumberLabel', () => {
  it('shows only the last path segment of a full URL', () => {
    expect(ticketNumberLabel('https://jira.example/browse/SHOP-12')).toBe('SHOP-12');
    expect(ticketNumberLabel('https://jira.example/browse/SHOP-12/')).toBe('SHOP-12');
  });

  it('leaves a plain ticket number unchanged', () => {
    expect(ticketNumberLabel('SHOP-12')).toBe('SHOP-12');
    expect(ticketNumberLabel('')).toBe('');
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

describe('splitTicketUrls', () => {
  it('returns master left and external right', () => {
    expect(
      splitTicketUrls('https://jira.example/browse/SHOP-1', 'https://ext.example/PS-9')
    ).toEqual({
      left: 'https://jira.example/browse/SHOP-1',
      right: 'https://ext.example/PS-9',
    });
  });

  it('returns null when either URL is missing or unsafe', () => {
    expect(splitTicketUrls(null, 'https://ext.example/PS-9')).toBeNull();
    expect(splitTicketUrls('https://jira.example/browse/A-1', 'not-a-url')).toBeNull();
    expect(splitTicketUrls('https://jira.example/browse/A-1', 'javascript:alert(1)')).toBeNull();
  });
});
