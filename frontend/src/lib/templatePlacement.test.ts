import { describe, expect, it } from 'vitest';
import type { FieldDef } from './api';
import { encodeFieldOrder, equalizeLineWidths, rebalanceLineWidths } from './fieldLayout';
import {
  displayRowNumber,
  displayWidth,
  dropOnLine,
  dropOnNewRow,
  insertIdAtSlot,
  lineOf,
  moveToAdjacentRow,
  moveToNewRow,
  moveWithinRow,
  openLineAfter,
  placeField,
  placements,
  reorderFieldsOnLine,
  resizeFromEdge,
  setFieldWidth,
  slotOf,
  sortFields,
  widthFromEdgePointer,
} from './templatePlacement';

function f(id: string, order: number | string, width?: number, extra: Partial<FieldDef> = {}): FieldDef {
  return { id, label: id, type: 'text', order, ...(width != null ? { width } : {}), ...extra };
}

/** Exact old TemplateEditor setPlacement (number inputs for Line / On line). */
function legacySetPlacement(draft: FieldDef[], id: string, line: number, slot: number): FieldDef[] {
  const i = draft.findIndex((x) => x.id === id);
  if (i < 0) return draft;
  const prevLine = lineOf(draft[i]);
  const row = Math.max(1, Math.floor(Number(line)) || 1);
  const col = Math.max(1, Math.floor(Number(slot)) || 1) - 1;
  const next = draft.map((x, idx) => (idx === i ? { ...x, order: encodeFieldOrder(row, col) } : x));
  let sorted = sortFields(next);
  if (prevLine !== row) {
    sorted = equalizeLineWidths(sorted, prevLine);
    sorted = equalizeLineWidths(sorted, row);
  }
  return sorted;
}

function legacySetWidth(draft: FieldDef[], id: string, value: number): FieldDef[] {
  const field = draft.find((x) => x.id === id);
  if (!field) return draft;
  return rebalanceLineWidths(draft, lineOf(field), field.id, value);
}

function byId(fields: FieldDef[]) {
  return placements(fields)
    .slice()
    .sort((a, b) => a.id.localeCompare(b.id));
}

describe('placeField matches old number inputs', () => {
  const start = [f('a', 10), f('b', '10b'), f('c', 20), f('d', '20b')];

  it('changing On line writes the same line/slot/width as the old control', () => {
    const viaDrag = placeField(start, 'b', 10, 1);
    const viaInput = legacySetPlacement(start, 'b', 10, 1);
    expect(byId(viaDrag)).toEqual(byId(viaInput));
  });

  it('changing Line writes the same line/slot/width as the old control', () => {
    const viaDrag = placeField(start, 'c', 10, 3);
    const viaInput = legacySetPlacement(start, 'c', 10, 3);
    expect(byId(viaDrag)).toEqual(byId(viaInput));
    expect(viaDrag.find((x) => x.id === 'c') && lineOf(viaDrag.find((x) => x.id === 'c')!)).toBe(10);
  });

  it('Width % input and drag edge-resize write the same widths and keep the row at 100', () => {
    const even = equalizeLineWidths([f('a', '10a'), f('b', '10b'), f('c', '10c')], 10);
    const viaDrag = resizeFromEdge(even, 'a', 50);
    const viaInput = legacySetWidth(even, 'a', 50);
    expect(byId(viaDrag)).toEqual(byId(viaInput));
    const onLine = viaDrag.filter((x) => lineOf(x) === 10);
    expect(onLine.reduce((acc, x) => acc + (x.width ?? 0), 0)).toBe(100);
  });
});

describe('drag reorder', () => {
  it('reordering within a row matches setting On line for each field in that order', () => {
    const start = [f('a', '10a'), f('b', '10b'), f('c', '10c')];
    const ordered = ['c', 'a', 'b'];
    const viaDrag = reorderFieldsOnLine(start, 10, ordered);
    let viaInputs = start;
    ordered.forEach((id, i) => {
      viaInputs = placeField(viaInputs, id, 10, i + 1);
    });
    expect(byId(viaDrag)).toEqual(byId(viaInputs));
    expect(viaDrag.filter((x) => lineOf(x) === 10).map((x) => x.id)).toEqual(expect.arrayContaining(ordered));
    expect(slotOf(viaDrag.find((x) => x.id === 'c')!)).toBe(1);
    expect(slotOf(viaDrag.find((x) => x.id === 'a')!)).toBe(2);
    expect(slotOf(viaDrag.find((x) => x.id === 'b')!)).toBe(3);
  });

  it('dropOnLine onto another row matches Line + On line, then compact slots', () => {
    const start = [f('a', 10), f('b', '10b'), f('c', 20)];
    const viaDrag = dropOnLine(start, 'c', 10, 2);
    let viaInputs = placeField(start, 'c', 10, 2);
    viaInputs = reorderFieldsOnLine(
      viaInputs,
      10,
      insertIdAtSlot(
        start.filter((x) => lineOf(x) === 10).map((x) => x.id),
        'c',
        2
      )
    );
    expect(byId(viaDrag)).toEqual(byId(viaInputs));
    expect(lineOf(viaDrag.find((x) => x.id === 'c')!)).toBe(10);
  });

  it('drop onto a new row matches placing Line to the open line at slot 1', () => {
    const start = [f('a', 10), f('b', '10b'), f('c', 20)];
    const viaDrag = dropOnNewRow(start, 'b', 10);
    const newLine = openLineAfter(start, 10);
    const viaInput = legacySetPlacement(start, 'b', newLine, 1);
    expect(byId(viaDrag)).toEqual(byId(viaInput));
    expect(lineOf(viaDrag.find((x) => x.id === 'b')!)).toBe(newLine);
  });

  it('keyboard move within a row swaps neighbors', () => {
    const start = [f('a', '10a'), f('b', '10b'), f('c', '10c')];
    const next = moveWithinRow(start, 'b', -1);
    expect(slotOf(next.find((x) => x.id === 'b')!)).toBe(1);
    expect(slotOf(next.find((x) => x.id === 'a')!)).toBe(2);
    expect(moveWithinRow(start, 'a', -1)).toEqual(start);
  });

  it('keyboard move to the next row uses the same placement as the Line input', () => {
    const start = [f('a', 10), f('b', 20), f('c', 30)];
    const next = moveToAdjacentRow(start, 'a', 1);
    expect(lineOf(next.find((x) => x.id === 'a')!)).toBe(20);
    const created = moveToNewRow(start, 'c');
    expect(lineOf(created.find((x) => x.id === 'c')!)).toBeGreaterThan(30);
  });
});

describe('edge resize pointer math', () => {
  it('maps the pointer to a 5–95 percent width', () => {
    expect(widthFromEdgePointer(0, 200, 100)).toBe(50);
    expect(widthFromEdgePointer(0, 200, 0)).toBe(5);
    expect(widthFromEdgePointer(0, 200, 200)).toBe(95);
  });

  it('setFieldWidth is the old Width % input', () => {
    const even = equalizeLineWidths([f('a', '10a'), f('b', '10b')], 10);
    expect(byId(setFieldWidth(even, 'a', 70))).toEqual(byId(legacySetWidth(even, 'a', 70)));
  });
});

describe('display rows', () => {
  it('numbers rows from 1 in visual order, not the stored line key', () => {
    const fields = [f('a', 10), f('b', 30)];
    expect(displayRowNumber(fields, 10)).toBe(1);
    expect(displayRowNumber(fields, 30)).toBe(2);
    expect(displayWidth(fields[0]!, fields)).toBe(100);
  });
});
