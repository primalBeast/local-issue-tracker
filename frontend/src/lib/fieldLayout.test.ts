import { describe, expect, it } from 'vitest';
import { groupFieldsByRow, parseFieldOrder } from './fieldLayout';
import type { FieldDef } from './api';

function f(id: string, order: number | string): FieldDef {
  return { id, label: id, type: 'text', order };
}

describe('parseFieldOrder', () => {
  it('parses numeric order', () => {
    expect(parseFieldOrder(10)).toEqual({ row: 10, col: 0, raw: 10 });
  });

  it('parses letter suffixes for columns', () => {
    expect(parseFieldOrder('10a').row).toBe(10);
    expect(parseFieldOrder('10a').col).toBe(0);
    expect(parseFieldOrder('10b').col).toBe(1);
    expect(parseFieldOrder('10c').col).toBe(2);
  });

  it('parses bare numeric string', () => {
    expect(parseFieldOrder('20')).toEqual({ row: 20, col: 0, raw: '20' });
  });
});

describe('groupFieldsByRow', () => {
  it('groups side-by-side fields on the same row', () => {
    const rows = groupFieldsByRow([
      f('notes', 90),
      f('state', '30b'),
      f('priority', '30a'),
      f('title', 20),
    ]);
    expect(rows.map((r) => r.row)).toEqual([20, 30, 90]);
    expect(rows[1].fields.map((x) => x.id)).toEqual(['priority', 'state']);
  });
});
