/** Numeric urgency, or null when the field is blank or not a number. */
export function urgencyRank(value: unknown): number | null {
  if (value == null || value === '' || typeof value === 'boolean') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Same rank cannot change list order by itself, so a plain swap is not enough. */
export function canSwapUrgency(a: unknown, b: unknown): boolean {
  return urgencyRank(a) !== urgencyRank(b);
}

export type UrgencyRow = { id: string; urgency: unknown };
export type UrgencyPatch = { id: string; urgency: number };

export type UrgencyMove = {
  patches: UrgencyPatch[];
  /** Visual order after the move. Used to keep ties stable once secondary sort is off. */
  orderIds: string[];
  /** True when the ticket moved into or through a block of equal urgencies. */
  clearSecondary: boolean;
};

function sameRankRunLength(order: UrgencyRow[], index: number): number {
  const rank = urgencyRank(order[index]?.urgency);
  let start = index;
  let end = index;
  while (start > 0 && urgencyRank(order[start - 1].urgency) === rank) start -= 1;
  while (end + 1 < order.length && urgencyRank(order[end + 1].urgency) === rank) end += 1;
  return end - start + 1;
}

/**
 * Move the ticket at `index` one visual slot (`delta` -1 up, +1 down).
 * A different urgency swaps. Moving into a block of the same urgency adopts
 * that value and leaves the ticket it replaces unchanged.
 */
export function planUrgencyMove(
  order: UrgencyRow[],
  index: number,
  delta: -1 | 1
): UrgencyMove | null {
  const target = index + delta;
  if (index < 0 || target < 0 || target >= order.length) return null;
  const dragged = order[index];
  const neighbor = order[target];
  const draggedRank = urgencyRank(dragged.urgency);
  const neighborRank = urgencyRank(neighbor.urgency);
  const intoBlock = neighborRank !== null && sameRankRunLength(order, target) >= 2;
  const next = order.map((item) => ({ id: item.id, urgency: item.urgency }));
  const [row] = next.splice(index, 1);
  next.splice(target, 0, row);
  const patches: UrgencyPatch[] = [];
  if (intoBlock || draggedRank === neighborRank) {
    if (neighborRank !== null && draggedRank !== neighborRank) {
      patches.push({ id: dragged.id, urgency: neighborRank });
    }
    return { patches, orderIds: next.map((item) => item.id), clearSecondary: true };
  }
  if (draggedRank !== neighborRank) {
    patches.push({ id: dragged.id, urgency: neighborRank ?? 0 });
    patches.push({ id: neighbor.id, urgency: draggedRank ?? 0 });
  }
  return patches.length
    ? { patches, orderIds: next.map((item) => item.id), clearSecondary: false }
    : null;
}

export type RowBand = { top: number; height: number };

/**
 * Which neighbor to swap with so the dragged row follows the pointer.
 * -1 is the row above, 1 is the row below. Null means stay put.
 * Rows are in the current visual (already sorted) order.
 */
export function urgencySwapDelta(
  index: number,
  pointerY: number,
  rows: RowBand[]
): -1 | 1 | null {
  const current = rows[index];
  if (!current || current.height <= 0) return null;
  const mid = current.top + current.height / 2;
  if (pointerY < mid) {
    const prev = rows[index - 1];
    if (prev && pointerY < prev.top + prev.height / 2) return -1;
    return null;
  }
  if (pointerY > mid) {
    const next = rows[index + 1];
    if (next && pointerY > next.top + next.height / 2) return 1;
  }
  return null;
}
