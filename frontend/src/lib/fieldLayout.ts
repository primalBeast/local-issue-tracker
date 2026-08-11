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

/** Optional flex weight for uneven columns (default 1). */
export function fieldFlex(def: FieldDef): number {
  const w = def.width_weight ?? def.flex;
  if (typeof w === 'number' && w > 0) return w;
  return 1;
}
