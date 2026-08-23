import { describe, expect, it } from 'vitest';
import type { FieldDef, Item, Panel } from './api';
import { sortItems } from './filters';
import { compareItemFields, layoutColumnMajor, sortItemPanels } from './panelSort';

function item(id: string, fields: Record<string, unknown>): Item {
  return {
    id,
    sort_key: 0,
    fields,
    created_at: '',
    updated_at: '',
    version: 1,
    waiting: {
      is_waiting: false,
      current_started_at: null,
      current_seconds: null,
      total_seconds: 0,
    },
  };
}

function panel(id: string, kind: Panel['kind'] = 'item'): Panel {
  return { id, kind, item_id: kind === 'item' ? id : undefined, x: 0, y: 0, width: 200, height: 100, z_index: 1 };
}

const defs: FieldDef[] = [
  { id: 'ticket_key', label: 'Ticket', type: 'text', order: 10 },
  { id: 'title', label: 'Description', type: 'text', order: 20 },
  { id: 'priority', label: 'Priority', type: 'number', order: '30a' },
  {
    id: 'urgency',
    label: 'Urgency',
    type: 'number',
    order: '30b',
    default: 5,
  },
  {
    id: 'state',
    label: 'State',
    type: 'select',
    order: '30c',
    options: ['Submitted', 'In fixing', 'Done'],
  },
];

describe('compareItemFields', () => {
  it('sorts ticket keys numerically', () => {
    const a = item('a', { ticket_key: 'ABC-10' });
    const b = item('b', { ticket_key: 'ABC-2' });
    expect(compareItemFields(b, a, 'ticket_key', defs)).toBeLessThan(0);
  });

  it('sorts urgency as integers', () => {
    const a = item('a', { urgency: 8 });
    const b = item('b', { urgency: 2 });
    expect(compareItemFields(b, a, 'urgency', defs)).toBeLessThan(0);
  });
});

describe('sortItemPanels', () => {
  it('keeps special panels first, then sorted items', () => {
    const items = {
      i2: item('i2', { priority: 8 }),
      i1: item('i1', { priority: 2 }),
    };
    const ordered = sortItemPanels(
      [panel('i2'), panel('notes', 'notes'), panel('i1')],
      (p) => (p.item_id ? items[p.item_id] : null),
      'priority',
      defs
    );
    expect(ordered.map((p) => p.id)).toEqual(['notes', 'i1', 'i2']);
  });
});

describe('layoutColumnMajor', () => {
  it('fills down, then starts a new column to the right', () => {
    const placed = layoutColumnMajor(
      [
        { id: 'a', width: 100, height: 80 },
        { id: 'b', width: 100, height: 80 },
        { id: 'c', width: 120, height: 80 },
      ],
      { x: 0, y: 0 },
      200,
      10,
      10
    );
    expect(placed[0]).toMatchObject({ x: 10, y: 10 });
    expect(placed[1].y).toBeGreaterThan(placed[0].y);
    expect(placed[2].x).toBeGreaterThan(placed[0].x);
    expect(placed[2].y).toBe(placed[0].y);
  });
});

describe('sortItems header toggle', () => {
  const list = [item('a', { priority: 3 }), item('b', { priority: 1 }), item('c', { priority: 2 })];

  it('sorts ascending then descending by the same field', () => {
    const asc = sortItems(list, { field: 'priority', direction: 'asc' }, defs);
    expect(asc.map((i) => i.fields.priority)).toEqual([1, 2, 3]);
    const desc = sortItems(list, { field: 'priority', direction: 'desc' }, defs);
    expect(desc.map((i) => i.fields.priority)).toEqual([3, 2, 1]);
  });
});

describe('waiting leftover values do not sort', () => {
  const waitingDefs: FieldDef[] = [
    ...defs,
    { id: 'waiting', label: 'Waiting', type: 'checkbox', order: 49 },
    { id: 'waiting_for', label: 'Name', type: 'text', order: '50a' },
    { id: 'waiting_since', label: 'Since', type: 'date', order: 51 },
  ];

  function waitingItem(
    id: string,
    fields: Record<string, unknown>,
    waiting?: Partial<Item['waiting']>
  ): Item {
    const it = item(id, fields);
    if (waiting) it.waiting = { ...it.waiting, ...waiting };
    return it;
  }

  it('ignores leftover Waiting For names when the checkbox is off', () => {
    const list = [
      waitingItem('idle-z', { waiting: false, waiting_for: 'Zed' }),
      waitingItem('wait-m', { waiting: true, waiting_for: 'Mia' }, { is_waiting: true }),
      waitingItem('wait-a', { waiting: true, waiting_for: 'Ann' }, { is_waiting: true }),
    ];
    const asc = sortItems(list, { field: 'waiting_for', direction: 'asc' }, waitingDefs);
    expect(asc.map((i) => i.id)).toEqual(['wait-a', 'wait-m', 'idle-z']);
  });

  it('ignores leftover Waiting Since dates when the checkbox is off', () => {
    const list = [
      waitingItem('idle-old', { waiting: false, waiting_since: '2020-01-01' }),
      waitingItem('wait-new', { waiting: true, waiting_since: '2026-08-01' }, { is_waiting: true }),
      waitingItem('wait-mid', { waiting: true, waiting_since: '2026-04-01' }, { is_waiting: true }),
    ];
    const asc = sortItems(list, { field: 'waiting_since', direction: 'asc' }, waitingDefs);
    expect(asc.map((i) => i.id)).toEqual(['wait-mid', 'wait-new', 'idle-old']);
  });
});
