import type { FieldDef, Item } from './api';
import { compareItemFields } from './panelSort';
import { isItemWaiting } from './waiting';

export function isVisible(def: FieldDef, fields: Record<string, unknown>): boolean {
  const vw = def.visible_when;
  if (!vw) return true;
  const value = fields[vw.field];
  if (Object.prototype.hasOwnProperty.call(vw, 'equals') && value !== vw.equals) {
    return false;
  }
  if (Object.prototype.hasOwnProperty.call(vw, 'not_equals') && value === vw.not_equals) {
    return false;
  }
  if (typeof vw.starts_with === 'string') {
    if (!String(value ?? '').startsWith(vw.starts_with)) return false;
  }
  return true;
}

export function itemMatchesFilters(
  item: Item,
  active: Record<string, unknown>,
  fieldDefs: FieldDef[]
): boolean {
  const byId = Object.fromEntries(fieldDefs.map((f) => [f.id, f]));
  for (const [fieldId, filterVal] of Object.entries(active || {})) {
    if (filterVal == null) continue;
    const def = byId[fieldId];
    const value = item.fields[fieldId];
    if (!def) continue;

    if (Array.isArray(filterVal)) {
      if (filterVal.length === 0) continue;
      if (def.type === 'multiselect' && Array.isArray(value)) {
        const hit = (value as string[]).some((v) => filterVal.includes(v));
        if (!hit) return false;
      } else if (def.type === 'checkbox') {
        if (!filterVal.includes(Boolean(value))) return false;
      } else {
        if (!filterVal.includes(value as string)) return false;
      }
    } else if (typeof filterVal === 'object' && filterVal !== null) {
      const { min, max } = filterVal as { min?: number; max?: number };
      const n = Number(value);
      if (min != null && n < min) return false;
      if (max != null && n > max) return false;
    }
  }
  return true;
}

export type ListSortDir = 'asc' | 'desc';
export type ListSortKey = { field: string; direction: ListSortDir };
export type ListSort = ListSortKey & { secondary?: ListSortKey };

function compareListField(a: Item, b: Item, field: string, defs: FieldDef[]): number {
  if (field === '_waiting') {
    const aw = isItemWaiting(a) ? (a.waiting?.current_seconds ?? 0) : -1;
    const bw = isItemWaiting(b) ? (b.waiting?.current_seconds ?? 0) : -1;
    return aw - bw;
  }
  if (field === '_updated') {
    return String(a.updated_at ?? '').localeCompare(String(b.updated_at ?? ''));
  }
  return compareItemFields(a, b, field, defs);
}

export function sortItems(
  items: Item[],
  sort: ListSort,
  defs: FieldDef[] = []
): Item[] {
  return [...items].sort((a, b) => {
    const dir = sort.direction === 'desc' ? -1 : 1;
    const primary = compareListField(a, b, sort.field, defs) * dir;
    if (primary !== 0) return primary;
    const secondary = sort.secondary;
    if (!secondary || secondary.field === sort.field) return 0;
    const sdir = secondary.direction === 'desc' ? -1 : 1;
    return compareListField(a, b, secondary.field, defs) * sdir;
  });
}
