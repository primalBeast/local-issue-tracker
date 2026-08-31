import { describe, expect, it } from 'vitest';
import { filledTicketSlots, slotsToShow, urlTail } from './urlTicket';

describe('urlTail', () => {
  it('takes the segment after the last slash or backslash', () => {
    expect(urlTail('https://jira.example/browse/SHOP-12')).toBe('SHOP-12');
    expect(urlTail('https://jira.example/browse/SHOP-12/')).toBe('SHOP-12');
    expect(urlTail('C:\\tickets\\FOO-1')).toBe('FOO-1');
    expect(urlTail('SHOP-9')).toBe('SHOP-9');
    expect(urlTail('  ')).toBe('');
  });
});

describe('slotsToShow', () => {
  it('keeps filled extra URLs visible and reveals empty slots on demand', () => {
    expect(filledTicketSlots({})).toBe(1);
    expect(slotsToShow(undefined, { external_ticket_3: 'https://x/a' })).toBe(3);
    expect(slotsToShow(2, {})).toBe(2);
    expect(slotsToShow(1, { external_ticket_2: 'https://x/b' })).toBe(2);
  });
});
