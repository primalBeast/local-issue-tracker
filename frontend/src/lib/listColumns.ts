/** Synthetic All Items columns that are not ticket fields. */
export const WAITING_COL = '_waiting';
export const UPDATED_COL = '_updated';

export type ListColumnPrefs = {
  /** Column ids, including ones the user has hidden, in their chosen order. */
  order?: string[];
  /** Explicit show/hide. Missing ids fall back to the field's show_in_list flag. */
  visible?: Record<string, boolean>;
};

export type ColumnField = {
  id: string;
  order?: number | string;
  show_in_list?: boolean;
};

function fieldRank(field: ColumnField | undefined): string {
  if (!field) return '\uffff';
  return String(field.order ?? '');
}

function byFieldOrder(a: ColumnField, b: ColumnField): number {
  return fieldRank(a).localeCompare(fieldRank(b), undefined, { numeric: true });
}

export function columnVisible(field: ColumnField, visible?: Record<string, boolean>): boolean {
  if (visible && Object.prototype.hasOwnProperty.call(visible, field.id)) return Boolean(visible[field.id]);
  return Boolean(field.show_in_list);
}

/** Default All Items order: listed fields, then Waiting, then Updated. */
export function defaultColumnOrder(fields: readonly ColumnField[], includeWaiting: boolean): string[] {
  const ids = fields
    .filter((f) => f.show_in_list)
    .slice()
    .sort(byFieldOrder)
    .map((f) => f.id);
  if (includeWaiting) ids.push(WAITING_COL);
  ids.push(UPDATED_COL);
  return ids;
}

function insertByFieldOrder(order: string[], fields: readonly ColumnField[], id: string): string[] {
  if (order.includes(id)) return order;
  const rankOf = (col: string) => fieldRank(fields.find((f) => f.id === col));
  const target = rankOf(id);
  const next = [...order];
  const idx = next.findIndex((col) => rankOf(col).localeCompare(target, undefined, { numeric: true }) > 0);
  next.splice(idx < 0 ? next.length : idx, 0, id);
  return next;
}

/** Visible column ids in the user's order. New columns land just before Waiting and Updated. */
export function orderedColumnIds(
  fields: readonly ColumnField[],
  prefs: ListColumnPrefs | null | undefined,
  includeWaiting: boolean
): string[] {
  const visible = new Set(
    fields.filter((f) => columnVisible(f, prefs?.visible)).map((f) => f.id)
  );
  if (includeWaiting) visible.add(WAITING_COL);
  visible.add(UPDATED_COL);

  let order = prefs?.order?.length ? [...prefs.order] : defaultColumnOrder(fields, includeWaiting);
  const missing = [...visible]
    .filter((id) => !order.includes(id))
    .sort((a, b) => fieldRank(fields.find((f) => f.id === a)).localeCompare(
      fieldRank(fields.find((f) => f.id === b)),
      undefined,
      { numeric: true }
    ));
  if (missing.length) {
    let idx = order.length;
    while (idx > 0 && (order[idx - 1] === WAITING_COL || order[idx - 1] === UPDATED_COL)) idx -= 1;
    order = [...order.slice(0, idx), ...missing, ...order.slice(idx)];
  }
  return order.filter((id) => visible.has(id));
}

/** Put a newly shown column into a saved order, just before Waiting and Updated. */
export function showColumnInOrder(order: readonly string[], id: string): string[] {
  if (order.includes(id)) return [...order];
  const next = [...order];
  let idx = next.length;
  while (idx > 0 && (next[idx - 1] === WAITING_COL || next[idx - 1] === UPDATED_COL)) idx -= 1;
  next.splice(idx, 0, id);
  return next;
}

export function moveColumn(order: readonly string[], fromId: string, toId: string, after = false): string[] {
  if (fromId === toId || !order.includes(fromId) || !order.includes(toId)) return [...order];
  const next = order.filter((id) => id !== fromId);
  let idx = next.indexOf(toId);
  if (after) idx += 1;
  next.splice(idx, 0, fromId);
  return next;
}

/**
 * Move one visible column. Hidden ids stay where they are relative to the columns that did not move.
 */
export function reorderColumns(
  stored: readonly string[] | undefined,
  visibleIds: readonly string[],
  fromId: string,
  toId: string,
  after = false
): string[] {
  const base = stored?.length ? [...stored] : [...visibleIds];
  for (const id of visibleIds) {
    if (!base.includes(id)) base.push(id);
  }
  return moveColumn(base, fromId, toId, after);
}
