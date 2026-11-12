import type { FieldDef } from './api';
import {
  encodeFieldOrder,
  equalizeLineWidths,
  fieldWidthPercent,
  parseFieldOrder,
  rebalanceLineWidths,
} from './fieldLayout';

/** Same fallback as the old TemplateEditor line number input. */
export function lineOf(f: FieldDef): number {
  const row = parseFieldOrder(f.order).row;
  return Number.isFinite(row) && row < Number.MAX_SAFE_INTEGER / 2 ? row : 10;
}

/** 1-based slot; same as the old "On line" control. */
export function slotOf(f: FieldDef): number {
  return parseFieldOrder(f.order).col + 1;
}

export function sortFields(fields: FieldDef[]): FieldDef[] {
  return [...fields].sort((a, b) => {
    const ao = parseFieldOrder(a.order);
    const bo = parseFieldOrder(b.order);
    if (ao.row !== bo.row) return ao.row - bo.row;
    if (ao.col !== bo.col) return ao.col - bo.col;
    return a.id.localeCompare(b.id);
  });
}

export function fieldsOnLine(fields: FieldDef[], line: number): FieldDef[] {
  return fields.filter((f) => lineOf(f) === line).sort((a, b) => slotOf(a) - slotOf(b) || a.id.localeCompare(b.id));
}

export function displayWidth(f: FieldDef, fields: FieldDef[]): number {
  return Math.round(fieldWidthPercent(f, fieldsOnLine(fields, lineOf(f))));
}

export type LineGroup = { line: number; fields: FieldDef[] };

export function groupFieldsByLine(fields: FieldDef[]): LineGroup[] {
  const map = new Map<number, FieldDef[]>();
  for (const f of fields) {
    const line = lineOf(f);
    const list = map.get(line);
    if (list) list.push(f);
    else map.set(line, [f]);
  }
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([line, group]) => ({
      line,
      fields: [...group].sort((a, b) => slotOf(a) - slotOf(b) || a.id.localeCompare(b.id)),
    }));
}

/** 1-based row index in the editor (Row 1, Row 2, …), not the stored line number. */
export function displayRowNumber(fields: FieldDef[], line: number): number {
  const lines = [...new Set(fields.map(lineOf))].sort((a, b) => a - b);
  const i = lines.indexOf(line);
  return i >= 0 ? i + 1 : lines.length + 1;
}

export function uniqueLines(fields: FieldDef[]): number[] {
  return [...new Set(fields.map(lineOf))].sort((a, b) => a - b);
}

/**
 * Old number-input placement: set Line + On line for one field.
 * Changing line equalizes both the old and new rows.
 */
export function placeField(fields: FieldDef[], id: string, line: number, slot: number): FieldDef[] {
  const i = fields.findIndex((f) => f.id === id);
  if (i < 0) return fields;
  const prevLine = lineOf(fields[i]);
  const row = Math.max(1, Math.floor(Number(line)) || 1);
  const col = Math.max(1, Math.floor(Number(slot)) || 1) - 1;
  let next = fields.map((f, idx) => (idx === i ? { ...f, order: encodeFieldOrder(row, col) } : f));
  if (prevLine !== row) {
    next = equalizeLineWidths(next, prevLine);
    next = equalizeLineWidths(next, row);
  }
  return next;
}

/** Old Width % number input. */
export function setFieldWidth(fields: FieldDef[], id: string, value: number): FieldDef[] {
  const f = fields.find((x) => x.id === id);
  if (!f) return fields;
  return rebalanceLineWidths(fields, lineOf(f), f.id, value);
}

/**
 * Drag the divider between two adjacent fields: same as typing the left
 * field's new width into the old Width % input.
 */
export function resizeFromEdge(fields: FieldDef[], leftId: string, newLeftWidth: number): FieldDef[] {
  return setFieldWidth(fields, leftId, newLeftWidth);
}

export function widthFromEdgePointer(rowLeft: number, rowWidth: number, clientX: number): number {
  if (rowWidth <= 0) return 50;
  const pct = ((clientX - rowLeft) / rowWidth) * 100;
  return Math.round(Math.min(95, Math.max(5, pct)));
}

/** Sequential "On line" assignments for every field on a row. */
export function reorderFieldsOnLine(fields: FieldDef[], line: number, orderedIds: string[]): FieldDef[] {
  const index = new Map(orderedIds.map((id, i) => [id, i]));
  return fields.map((f) => {
    if (lineOf(f) !== line && !index.has(f.id)) return f;
    const slot = index.get(f.id);
    if (slot == null) return f;
    return { ...f, order: encodeFieldOrder(line, slot) };
  });
}

export function insertIdAtSlot(ids: string[], draggedId: string, slot: number): string[] {
  const without = ids.filter((id) => id !== draggedId);
  const at = Math.max(0, Math.min(without.length, Math.floor(Number(slot)) - 1));
  const next = [...without];
  next.splice(at, 0, draggedId);
  return next;
}

export function openLineAfter(fields: FieldDef[], afterLine: number): number {
  const lines = uniqueLines(fields);
  const i = lines.indexOf(afterLine);
  const nextLine = i >= 0 ? lines[i + 1] : undefined;
  if (nextLine != null && nextLine - afterLine > 1) {
    return afterLine + Math.floor((nextLine - afterLine) / 2);
  }
  const max = lines.length ? Math.max(...lines) : 0;
  return max + 10;
}

export function openLineBefore(fields: FieldDef[], beforeLine: number): number {
  const lines = uniqueLines(fields);
  const i = lines.indexOf(beforeLine);
  const prev = i > 0 ? lines[i - 1] : undefined;
  if (prev == null) {
    if (beforeLine > 1) return Math.max(1, Math.floor(beforeLine / 2));
    const max = lines.length ? Math.max(...lines) : 0;
    return max + 10;
  }
  if (beforeLine - prev > 1) return prev + Math.floor((beforeLine - prev) / 2);
  const max = lines.length ? Math.max(...lines) : 0;
  return max + 10;
}

/** Drop onto an existing row. Same-row drop re-encodes slots; cross-row uses placeField then re-encodes. */
export function dropOnLine(fields: FieldDef[], draggedId: string, line: number, slot: number): FieldDef[] {
  const current = fields.find((f) => f.id === draggedId);
  if (!current) return fields;
  const prevLine = lineOf(current);
  const targetIds = fields.filter((f) => lineOf(f) === line && f.id !== draggedId).map((f) => f.id);
  const ordered = insertIdAtSlot(targetIds, draggedId, slot);
  const currentIds = fieldsOnLine(fields, line).map((f) => f.id);
  if (prevLine === line && currentIds.join('\0') === ordered.join('\0')) return fields;
  let next = fields;
  if (prevLine !== line) next = placeField(next, draggedId, line, slot);
  return reorderFieldsOnLine(next, line, ordered);
}

export function dropOnNewRow(fields: FieldDef[], draggedId: string, afterLine: number | null): FieldDef[] {
  const line = afterLine == null ? openLineBefore(fields, uniqueLines(fields)[0] ?? 10) : openLineAfter(fields, afterLine);
  return placeField(fields, draggedId, line, 1);
}

export function moveWithinRow(fields: FieldDef[], id: string, delta: -1 | 1): FieldDef[] {
  const current = fields.find((f) => f.id === id);
  if (!current) return fields;
  const line = lineOf(current);
  const ids = fieldsOnLine(fields, line).map((f) => f.id);
  const i = ids.indexOf(id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= ids.length) return fields;
  const next = [...ids];
  const a = next[i];
  const b = next[j];
  if (a == null || b == null) return fields;
  next[i] = b;
  next[j] = a;
  return reorderFieldsOnLine(fields, line, next);
}

export function moveToAdjacentRow(fields: FieldDef[], id: string, delta: -1 | 1): FieldDef[] {
  const current = fields.find((f) => f.id === id);
  if (!current) return fields;
  const line = lineOf(current);
  const lines = uniqueLines(fields);
  const i = lines.indexOf(line);
  const nextLine = i >= 0 ? lines[i + delta] : undefined;
  if (nextLine == null) return fields;
  const slot = Math.min(slotOf(current), fieldsOnLine(fields, nextLine).length + 1);
  return dropOnLine(fields, id, nextLine, slot);
}

export function moveToNewRow(fields: FieldDef[], id: string): FieldDef[] {
  const current = fields.find((f) => f.id === id);
  if (!current) return fields;
  return dropOnNewRow(fields, id, lineOf(current));
}

export type Placement = { id: string; line: number; slot: number; width: number | undefined; order: FieldDef['order'] };

export function placements(fields: FieldDef[]): Placement[] {
  return fields.map((f) => ({
    id: f.id,
    line: lineOf(f),
    slot: slotOf(f),
    width: f.width,
    order: f.order,
  }));
}
