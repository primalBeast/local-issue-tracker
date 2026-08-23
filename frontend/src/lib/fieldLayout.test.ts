import { describe, expect, it } from 'vitest';
import {
  encodeFieldOrder,
  equalizeLineWidths,
  fieldWidthPercent,
  groupBodyBlocks,
  groupFieldsByRow,
  parseFieldOrder,
  rebalanceLineWidths,
} from './fieldLayout';
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

describe('encodeFieldOrder', () => {
  it('uses a plain number for the first control on a line', () => {
    expect(encodeFieldOrder(10, 0)).toBe(10);
  });

  it('uses letter suffixes for 2nd and 3rd on a line', () => {
    expect(encodeFieldOrder(30, 1)).toBe('30b');
    expect(encodeFieldOrder(30, 2)).toBe('30c');
  });

  it('round-trips through parseFieldOrder', () => {
    expect(parseFieldOrder(encodeFieldOrder(51, 0)).col).toBe(0);
    expect(parseFieldOrder(encodeFieldOrder(51, 3)).col).toBe(3);
  });
});

describe('line widths', () => {
  it('defaults to an even split when width is omitted', () => {
    const a = f('a', '10a');
    const b = f('b', '10b');
    expect(fieldWidthPercent(a, [a, b])).toBe(50);
    expect(fieldWidthPercent(b, [a, b])).toBe(50);
  });

  it('equalizes a line to 100%', () => {
    const fields = [f('a', '10a'), f('b', '10b'), f('c', '10c')];
    const next = equalizeLineWidths(fields, 10);
    expect(next.map((x) => x.width)).toEqual([33, 33, 34]);
  });

  it('scales the others on a line when one width changes', () => {
    const fields = equalizeLineWidths([f('a', '10a'), f('b', '10b'), f('c', '10c')], 10);
    const next = rebalanceLineWidths(fields, 10, 'a', 50);
    expect(next.find((x) => x.id === 'a')?.width).toBe(50);
    expect(next.find((x) => x.id === 'b')?.width).toBe(25);
    expect(next.find((x) => x.id === 'c')?.width).toBe(25);
    const sum = next.reduce((acc, x) => acc + (x.width ?? 0), 0);
    expect(sum).toBe(100);
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

describe('groupBodyBlocks', () => {
  it('pulls waiting checkbox, name, and since into one block before notes', () => {
    const rows = groupFieldsByRow([
      f('priority', '30a'),
      f('waiting', '49'),
      f('waiting_for', '50a'),
      f('waiting_for_reason', '50b'),
      f('waiting_since', 51),
      f('notes', 60),
    ]);
    const blocks = groupBodyBlocks(rows);
    expect(blocks.map((b) => b.kind)).toEqual(['row', 'waiting', 'row']);
    if (blocks[1].kind !== 'waiting') throw new Error('expected waiting');
    expect(blocks[1].fields.map((x) => x.id).sort()).toEqual([
      'waiting',
      'waiting_for',
      'waiting_for_reason',
      'waiting_since',
    ]);
  });
});
