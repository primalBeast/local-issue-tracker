import type { FieldDef, Item, Panel } from './api';
import { isItemWaiting } from './waiting';

const WAITING_VALUE_FIELDS = new Set(['waiting_for', 'waiting_since']);

export const PANEL_SORT_OPTIONS = [
  { id: 'ticket_key', label: 'Ticket number' },
  { id: 'title', label: 'Description' },
  { id: 'priority', label: 'Priority' },
  { id: 'urgency', label: 'Urgency' },
  { id: 'state', label: 'State' },
] as const;

export type PanelSortField = (typeof PANEL_SORT_OPTIONS)[number]['id'];

export function isPanelSortField(id: string): id is PanelSortField {
  return PANEL_SORT_OPTIONS.some((o) => o.id === id);
}

function fieldValue(item: Item, field: string, defs: FieldDef[]): unknown {
  if (WAITING_VALUE_FIELDS.has(field) && !isItemWaiting(item)) return '';
  const raw = item.fields[field];
  if (raw != null && raw !== '') return raw;
  const def = defs.find((d) => d.id === field);
  return def?.default ?? raw;
}

export function compareItemFields(
  a: Item | null,
  b: Item | null,
  field: string,
  defs: FieldDef[]
): number {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  const av = fieldValue(a, field, defs);
  const bv = fieldValue(b, field, defs);
  if (av == null || av === '') return bv == null || bv === '' ? 0 : 1;
  if (bv == null || bv === '') return -1;
  if (typeof av === 'number' && typeof bv === 'number') return av - bv;
  const def = defs.find((d) => d.id === field);
  if (def?.type === 'select' && def.options?.length) {
    const ia = def.options.indexOf(String(av));
    const ib = def.options.indexOf(String(bv));
    return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
  }
  return String(av).localeCompare(String(bv), undefined, {
    numeric: true,
    sensitivity: 'base',
  });
}

export function sortItemPanels(
  panels: Panel[],
  itemsById: (panel: Panel) => Item | null,
  field: string,
  defs: FieldDef[]
): Panel[] {
  const special = panels.filter((p) => p.kind !== 'item');
  const items = panels
    .filter((p) => p.kind === 'item')
    .sort((a, b) => {
      const c = compareItemFields(itemsById(a), itemsById(b), field, defs);
      if (c !== 0) return c;
      return a.id.localeCompare(b.id);
    });
  return [...special, ...items];
}

/** Pack panels top-to-bottom, then the next column to the right. */
export function layoutColumnMajor<T extends { width: number; height: number }>(
  panels: T[],
  origin: { x: number; y: number },
  viewHeight: number,
  gap = 16,
  pad = 24
): Array<T & { x: number; y: number }> {
  const startX = origin.x + pad;
  const startY = origin.y + pad;
  const limitY = origin.y + Math.max(viewHeight, pad + 80);
  let x = startX;
  let y = startY;
  let colW = 0;
  return panels.map((p) => {
    if (y > startY && y + p.height > limitY - pad) {
      x += colW + gap;
      y = startY;
      colW = 0;
    }
    const placed = { ...p, x, y };
    colW = Math.max(colW, p.width);
    y += p.height + gap;
    return placed;
  });
}
