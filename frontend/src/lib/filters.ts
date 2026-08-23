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

export function sortItems(
  items: Item[],
  sort: { field: string; direction: 'asc' | 'desc' },
  defs: FieldDef[] = []
): Item[] {
  const dir = sort.direction === 'desc' ? -1 : 1;
  return [...items].sort((a, b) => {
    if (sort.field === '_waiting') {
      const aw = isItemWaiting(a) ? (a.waiting?.current_seconds ?? 0) : -1;
      const bw = isItemWaiting(b) ? (b.waiting?.current_seconds ?? 0) : -1;
      return (aw - bw) * dir;
    }
    return compareItemFields(a, b, sort.field, defs) * dir;
  });
}
