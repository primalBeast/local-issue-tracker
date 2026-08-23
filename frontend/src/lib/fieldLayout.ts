import type { FieldDef } from './api';

export type ParsedOrder = {
  /** Row key for grouping (numeric portion of order). */
  row: number;
  /** Column index within the row (a=0, b=1, …). */
  col: number;
  raw: string | number;
};

/**
 * Parse field order into a row + column.
 *
 * - Number `10` → row 10, col 0 (full row if alone)
 * - String `"10"` → same
 * - String `"10a"` / `"10b"` → row 10, col 0 / 1 (side by side)
 * - Multi-letter `"10aa"` supported (base-26 after `a`)
 */
export function parseFieldOrder(order: number | string | undefined | null): ParsedOrder {
  if (order == null) {
    return { row: Number.MAX_SAFE_INTEGER, col: 0, raw: '' };
  }
  if (typeof order === 'number' && Number.isFinite(order)) {
    return { row: order, col: 0, raw: order };
  }
  const s = String(order).trim();
  const m = /^(\d+)([a-zA-Z]*)$/.exec(s);
  if (!m) {
    // Non-standard: keep stable sort via string code points after numbers
    return { row: Number.MAX_SAFE_INTEGER - 1, col: 0, raw: s };
  }
  const row = parseInt(m[1], 10);
  const letters = (m[2] || 'a').toLowerCase();
  let col = 0;
  for (const ch of letters) {
    col = col * 26 + (ch.charCodeAt(0) - 96);
  }
  col = Math.max(0, col - 1); // a → 0
  return { row, col, raw: s };
}

function colIndexToLetters(col: number): string {
  let n = Math.max(0, Math.floor(col)) + 1;
  let out = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(97 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

/** Inverse of parseFieldOrder: row 30, col 0 → 30; col 1 → "30b". */
export function encodeFieldOrder(row: number, col: number): string | number {
  const r = Math.max(0, Math.floor(Number(row)) || 0);
  const c = Math.max(0, Math.floor(Number(col)) || 0);
  if (c === 0) return r;
  return `${r}${colIndexToLetters(c)}`;
}

export type FieldRow = {
  row: number;
  fields: FieldDef[];
};

/** Sort fields and group into horizontal rows by order row number. */
export function groupFieldsByRow(fields: FieldDef[]): FieldRow[] {
  const decorated = fields.map((f) => ({ f, o: parseFieldOrder(f.order) }));
  decorated.sort((a, b) => {
    if (a.o.row !== b.o.row) return a.o.row - b.o.row;
    if (a.o.col !== b.o.col) return a.o.col - b.o.col;
    return a.f.id.localeCompare(b.f.id);
  });

  const rows: FieldRow[] = [];
  for (const { f, o } of decorated) {
    const last = rows[rows.length - 1];
    if (last && last.row === o.row) {
      last.fields.push(f);
    } else {
      rows.push({ row: o.row, fields: [f] });
    }
  }
  return rows;
}

function lineRow(def: FieldDef): number {
  return parseFieldOrder(def.order).row;
}

function weightOf(def: FieldDef): number {
  if (typeof def.width === 'number' && Number.isFinite(def.width) && def.width > 0) {
    return def.width;
  }
  const w = def.width_weight ?? def.flex;
  if (typeof w === 'number' && w > 0) return w;
  return 1;
}

/** Percent of the line this control occupies (siblings should be the fields on that line). */
export function fieldWidthPercent(def: FieldDef, siblings: FieldDef[]): number {
  if (!siblings.length) return 100;
  if (siblings.length === 1) return 100;
  const sum = siblings.reduce((acc, f) => acc + weightOf(f), 0) || siblings.length;
  return (weightOf(def) / sum) * 100;
}

/** Flex grow factor; uses width % when set, otherwise width_weight among siblings. */
export function fieldFlex(def: FieldDef, siblings: FieldDef[] = [def]): number {
  return fieldWidthPercent(def, siblings);
}

export function isWidthLocked(def: FieldDef): boolean {
  return Boolean(def.width_lock);
}

function applyWidths(fields: FieldDef[], map: Map<string, number>): FieldDef[] {
  return fields.map((f) => (map.has(f.id) ? { ...f, width: map.get(f.id)! } : f));
}

function splitInts(count: number, total: number, min: number, shares?: number[]): number[] {
  if (count <= 0) return [];
  if (count === 1) return [total];
  const floorMin = Math.max(0, min);
  const weights = shares && shares.length === count ? shares : Array(count).fill(1);
  const weightSum = weights.reduce((a, b) => a + b, 0) || count;
  const out: number[] = [];
  let used = 0;
  for (let i = 0; i < count; i++) {
    if (i === count - 1) {
      out.push(Math.max(floorMin, total - used));
      break;
    }
    const part = Math.max(floorMin, Math.round(total * (weights[i] / weightSum)));
    out.push(part);
    used += part;
  }
  const extra = total - out.reduce((a, b) => a + b, 0);
  if (extra !== 0) out[out.length - 1] += extra;
  return out;
}

export function equalizeLineWidths(fields: FieldDef[], line: number): FieldDef[] {
  const onLine = fields.filter((f) => lineRow(f) === line);
  if (!onLine.length) return fields;
  const locked = onLine.filter(isWidthLocked);
  const unlocked = onLine.filter((f) => !isWidthLocked(f));
  const map = new Map<string, number>();
  let lockedSum = 0;
  for (const f of locked) {
    const w = Math.round(fieldWidthPercent(f, onLine));
    map.set(f.id, w);
    lockedSum += w;
  }
  if (!unlocked.length) return applyWidths(fields, map);
  const rest = Math.max(0, 100 - lockedSum);
  const parts = splitInts(unlocked.length, rest, unlocked.length ? 1 : 0);
  unlocked.forEach((f, i) => map.set(f.id, parts[i]));
  return applyWidths(fields, map);
}

/** Set one field’s width % and scale unlocked others on that line so they sum to 100. */
export function rebalanceLineWidths(
  fields: FieldDef[],
  line: number,
  changedId: string,
  newWidth: number,
  minPct = 5
): FieldDef[] {
  const onLine = fields.filter((f) => lineRow(f) === line);
  if (!onLine.length) return fields;
  if (onLine.length === 1) {
    return fields.map((f) => (f.id === onLine[0].id ? { ...f, width: 100 } : f));
  }
  const others = onLine.filter((f) => f.id !== changedId);
  const lockedOthers = others.filter(isWidthLocked);
  const unlockedOthers = others.filter((f) => !isWidthLocked(f));
  const map = new Map<string, number>();
  let lockedSum = 0;
  for (const f of lockedOthers) {
    const lw = Math.round(fieldWidthPercent(f, onLine));
    map.set(f.id, lw);
    lockedSum += lw;
  }
  const min = Math.max(1, Math.min(minPct, Math.floor(100 / Math.max(2, unlockedOthers.length + 1))));
  const minUnlocked = min * unlockedOthers.length;
  const maxW = Math.max(min, 100 - lockedSum - minUnlocked);
  let w = Math.round(Number(newWidth));
  if (!Number.isFinite(w)) w = Math.round((100 - lockedSum) / Math.max(1, unlockedOthers.length + 1));
  w = Math.min(maxW, Math.max(min, w));
  map.set(changedId, w);
  const rest = 100 - lockedSum - w;
  if (!unlockedOthers.length) {
    map.set(changedId, 100 - lockedSum);
    return applyWidths(fields, map);
  }
  const shares = unlockedOthers.map((f) => fieldWidthPercent(f, unlockedOthers));
  const parts = splitInts(unlockedOthers.length, rest, min, shares);
  unlockedOthers.forEach((f, i) => map.set(f.id, parts[i]));
  const total = [...map.values()].reduce((a, b) => a + b, 0);
  if (total !== 100 && unlockedOthers.length) {
    const lastId = unlockedOthers[unlockedOthers.length - 1].id;
    map.set(lastId, (map.get(lastId) ?? 0) + (100 - total));
  }
  return applyWidths(fields, map);
}

const WAITING_LAYOUT_IDS = new Set(['waiting', 'waiting_for', 'waiting_since', 'waiting_for_reason']);

export type BodyBlock =
  | { kind: 'row'; row: FieldRow }
  | { kind: 'waiting'; fields: FieldDef[] };

/** Pull waiting fields into one two-column block (person+since | reason). */
export function groupBodyBlocks(rows: FieldRow[]): BodyBlock[] {
  const waiting: FieldDef[] = [];
  const out: BodyBlock[] = [];
  for (const row of rows) {
    const wait = row.fields.filter((f) => WAITING_LAYOUT_IDS.has(f.id));
    const other = row.fields.filter((f) => !WAITING_LAYOUT_IDS.has(f.id));
    waiting.push(...wait);
    if (other.length) out.push({ kind: 'row', row: { row: row.row, fields: other } });
  }
  if (!waiting.length) return out;
  const notesIdx = out.findIndex(
    (b) => b.kind === 'row' && b.row.fields.some((f) => f.id === 'notes' || f.type === 'richtext')
  );
  const block: BodyBlock = { kind: 'waiting', fields: waiting };
  if (notesIdx >= 0) out.splice(notesIdx, 0, block);
  else out.push(block);
  return out;
}

export function pickField(fields: FieldDef[], id: string): FieldDef | undefined {
  return fields.find((f) => f.id === id);
}
