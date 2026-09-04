import { describe, expect, it } from 'vitest';
import type { FieldDef, Item } from './api';
import { isVisible, itemMatchesFilters, itemMatchesSearch, sortItems } from './filters';

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

describe('itemMatchesSearch', () => {
  function item(fields: Record<string, unknown>, extra: Partial<Item> = {}): Item {
    return { id: 'x', updated_at: '', fields, ...extra } as Item;
  }

  it('matches any field, case-insensitive, and ignores blank queries', () => {
    const it = item({ ticket_key: 'NEW-12', title: 'Fix login', priority: 88 });
    expect(itemMatchesSearch(it, '')).toBe(true);
    expect(itemMatchesSearch(it, '  ')).toBe(true);
    expect(itemMatchesSearch(it, 'login')).toBe(true);
    expect(itemMatchesSearch(it, 'NEW-12')).toBe(true);
    expect(itemMatchesSearch(it, '88')).toBe(true);
    expect(itemMatchesSearch(it, 'xyz')).toBe(false);
  });

  it('matches TipTap notes text and does not join neighboring fields', () => {
    const notes = {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: 'omega' }] }],
    };
    expect(itemMatchesSearch(item({ title: 'aa', state: 'bb' }), 'aabb')).toBe(false);
    expect(itemMatchesSearch(item({ notes }), 'omega')).toBe(true);
    expect(itemMatchesSearch(item({ alternate_ticket: 'PROJ-99' }), 'proj-99')).toBe(true);
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

  it('breaks primary ties with the secondary column', () => {
    const defs: FieldDef[] = [
      field({ id: 'priority', type: 'number' }),
      field({ id: 'state', type: 'text' }),
    ];
    const list: Item[] = [
      { id: 'a', updated_at: '', fields: { priority: 1, state: 'B' } } as Item,
      { id: 'b', updated_at: '', fields: { priority: 1, state: 'A' } } as Item,
      { id: 'c', updated_at: '', fields: { priority: 2, state: 'A' } } as Item,
    ];
    const out = sortItems(
      list,
      { field: 'priority', direction: 'asc', secondary: { field: 'state', direction: 'asc' } },
      defs
    );
    expect(out.map((i) => i.id)).toEqual(['b', 'a', 'c']);
  });
});
