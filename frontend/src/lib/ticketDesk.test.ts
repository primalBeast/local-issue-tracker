import { describe, expect, it } from 'vitest';
import type { Item } from './api';
import { isOverdue, isStale, itemSummaryText } from './ticketDesk';

function item(fields: Record<string, unknown>, updated_at = '2026-10-01T00:00:00Z'): Item {
  return {
    id: '1',
    sort_key: 0,
    fields,
    created_at: updated_at,
    updated_at,
    version: 1,
    waiting: {
      is_waiting: false,
      current_started_at: null,
      current_seconds: null,
      total_seconds: 0,
    },
  };
}

describe('ticket desk', () => {
  it('marks a past due date overdue unless the ticket is Done', () => {
    expect(isOverdue(item({ due_on: '2026-10-01', state: 'In fixing' }), '2026-10-10')).toBe(true);
    expect(isOverdue(item({ due_on: '2026-10-10', state: 'In fixing' }), '2026-10-10')).toBe(false);
    expect(isOverdue(item({ due_on: '2026-10-01', state: 'Done' }), '2026-10-10')).toBe(false);
    expect(isOverdue(item({ due_on: 'tomorrow', state: 'In fixing' }), '2026-10-10')).toBe(false);
  });

  it('marks untouched open tickets stale after 14 days', () => {
    const now = Date.parse('2026-10-10T00:00:00Z');
    expect(isStale(item({ state: 'Submitted' }, '2026-09-01T00:00:00Z'), now)).toBe(true);
    expect(isStale(item({ state: 'Submitted' }, '2026-10-09T00:00:00Z'), now)).toBe(false);
    expect(isStale(item({ state: 'Done' }, '2026-09-01T00:00:00Z'), now)).toBe(false);
  });

  it('builds a plain summary', () => {
    const text = itemSummaryText(
      item({
        ticket_key: 'SHOP-1',
        title: 'Drawer jam',
        state: 'In fixing',
        priority: 1,
        due_on: '2026-10-01',
        pinned: true,
      })
    );
    expect(text).toContain('SHOP-1');
    expect(text).toContain('Drawer jam');
    expect(text).toContain('Pinned');
    expect(text).toContain('Due: 2026-10-01');
  });
});
