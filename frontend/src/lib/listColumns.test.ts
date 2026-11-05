import { describe, expect, it } from 'vitest';
import {
  UPDATED_COL,
  WAITING_COL,
  columnVisible,
  defaultColumnOrder,
  moveColumn,
  orderedColumnIds,
  reorderColumns,
  showColumnInOrder,
} from './listColumns';

const fields = [
  { id: 'ticket_key', order: 10, show_in_list: true },
  { id: 'alternate_ticket', order: 15, show_in_list: true },
  { id: 'title', order: 20, show_in_list: true },
  { id: 'notes', order: 60, show_in_list: false },
  { id: 'waiting_since', order: 51, show_in_list: false },
];

describe('list columns', () => {
  it('starts with listed fields, then Waiting, then Updated', () => {
    expect(defaultColumnOrder(fields, true)).toEqual([
      'ticket_key',
      'alternate_ticket',
      'title',
      WAITING_COL,
      UPDATED_COL,
    ]);
  });

  it('shows a hidden field and hides a listed one when asked', () => {
    const visible = { notes: true, title: false };
    expect(columnVisible(fields[2]!, visible)).toBe(false);
    expect(columnVisible(fields[3]!, visible)).toBe(true);
    expect(orderedColumnIds(fields, { visible }, false)).toEqual([
      'ticket_key',
      'alternate_ticket',
      'notes',
      UPDATED_COL,
    ]);
  });

  it('keeps a dragged order and adds a newly shown field before Waiting', () => {
    const order = ['title', 'ticket_key', WAITING_COL, UPDATED_COL];
    expect(orderedColumnIds(fields, { order, visible: { notes: true } }, true)).toEqual([
      'title',
      'ticket_key',
      'alternate_ticket',
      'notes',
      WAITING_COL,
      UPDATED_COL,
    ]);
  });

  it('inserts a newly shown column without forgetting a hidden one', () => {
    const stored = ['ticket_key', 'notes', 'title', WAITING_COL, UPDATED_COL];
    const order = showColumnInOrder(stored, 'alternate_ticket');
    expect(order).toEqual([
      'ticket_key',
      'notes',
      'title',
      'alternate_ticket',
      WAITING_COL,
      UPDATED_COL,
    ]);
    expect(orderedColumnIds(fields, { order, visible: { notes: false } }, true)).toEqual([
      'ticket_key',
      'title',
      'alternate_ticket',
      WAITING_COL,
      UPDATED_COL,
    ]);
  });

  it('moves a column before or after the drop target', () => {
    const order = ['a', 'b', 'c'];
    expect(moveColumn(order, 'c', 'a')).toEqual(['c', 'a', 'b']);
    expect(moveColumn(order, 'a', 'c', true)).toEqual(['b', 'c', 'a']);
    expect(moveColumn(order, 'a', 'a')).toEqual(order);
  });

  it('remembers a hidden column position while the visible ones move', () => {
    const stored = ['ticket_key', 'notes', 'title', UPDATED_COL];
    const visible = ['ticket_key', 'title', UPDATED_COL];
    expect(reorderColumns(stored, visible, 'title', 'ticket_key')).toEqual([
      'title',
      'ticket_key',
      'notes',
      UPDATED_COL,
    ]);
  });
});
