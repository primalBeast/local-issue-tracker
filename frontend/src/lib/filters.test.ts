import { describe, expect, it } from 'vitest';
import type { FieldDef, Item } from './api';
import { isVisible, itemMatchesFilters, sortItems } from './filters';

function field(partial: Partial<FieldDef> & Pick<FieldDef, 'id' | 'type'>): FieldDef {
  return { label: partial.id, order: 1, ...partial };
}

describe('isVisible', () => {
  it('hides the waiting checkbox when state is Done', () => {
    const def = field({
      id: 'waiting',
      type: 'checkbox',
      visible_when: { field: 'state', not_equals: 'Done' },
    });
    expect(isVisible(def, { state: 'Submitted' })).toBe(true);
    expect(isVisible(def, { state: 'Done' })).toBe(false);
  });

  it('shows name/since only when waiting is checked', () => {
    const def = field({
      id: 'waiting_for',
      type: 'text',
      visible_when: { field: 'waiting', equals: true },
    });
    expect(isVisible(def, { waiting: true })).toBe(true);
    expect(isVisible(def, { waiting: false })).toBe(false);
  });

  it('shows external ticket fields when state starts with External Fixing', () => {
    const def = field({
      id: 'external_ticket',
      type: 'url',
      visible_when: { field: 'state', starts_with: 'External Fixing' },
    });
    expect(isVisible(def, { state: 'External Fixing – Support' })).toBe(true);
    expect(isVisible(def, { state: 'External Fixing – PS' })).toBe(true);
    expect(isVisible(def, { state: 'Submitted' })).toBe(false);
    expect(isVisible(def, { state: 'In fixing' })).toBe(false);
  });
});

describe('itemMatchesFilters', () => {
  it('filters the waiting checkbox', () => {
    const defs = [field({ id: 'waiting', type: 'checkbox' })];
    const waiting = { fields: { waiting: true } } as never;
    const idle = { fields: { waiting: false } } as never;
    expect(itemMatchesFilters(waiting, { waiting: [true] }, defs)).toBe(true);
    expect(itemMatchesFilters(idle, { waiting: [true] }, defs)).toBe(false);
  });
});

describe('sortItems', () => {
  it('sorts by updated_at', () => {
    const a = { id: 'a', updated_at: '2026-08-01T12:00:00Z', fields: {} } as Item;
    const b = { id: 'b', updated_at: '2026-08-20T12:00:00Z', fields: {} } as Item;
    const asc = sortItems([b, a], { field: '_updated', direction: 'asc' });
    expect(asc.map((i) => i.id)).toEqual(['a', 'b']);
    const desc = sortItems([a, b], { field: '_updated', direction: 'desc' });
    expect(desc.map((i) => i.id)).toEqual(['b', 'a']);
  });
});
