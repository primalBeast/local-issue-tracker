import { describe, expect, it } from 'vitest';
import {
  canSwapUrgency,
  planUrgencyMove,
  urgencyRank,
  urgencySwapDelta,
  type RowBand,
  type UrgencyRow,
} from './urgencyReorder';

function tickets(...values: number[]): UrgencyRow[] {
  return values.map((urgency, i) => ({ id: String.fromCharCode(65 + i), urgency }));
}

function mapOf(patches: { id: string; urgency: number }[] | null) {
  return Object.fromEntries((patches ?? []).map((p) => [p.id, p.urgency]));
}

const rows: RowBand[] = [
  { top: 0, height: 20 },
  { top: 20, height: 20 },
  { top: 40, height: 20 },
];

describe('urgency reorder', () => {
  it('treats blank and non-numbers as no rank', () => {
    expect(urgencyRank(null)).toBeNull();
    expect(urgencyRank('')).toBeNull();
    expect(urgencyRank('nope')).toBeNull();
    expect(urgencyRank(8)).toBe(8);
    expect(urgencyRank('12')).toBe(12);
  });

  it('swaps only when the two ranks differ', () => {
    expect(canSwapUrgency(8, 2)).toBe(true);
    expect(canSwapUrgency(8, 8)).toBe(false);
    expect(canSwapUrgency(null, null)).toBe(false);
    expect(canSwapUrgency(null, 5)).toBe(true);
  });

  it('swaps upward once the pointer crosses the row above', () => {
    expect(urgencySwapDelta(1, 8, rows)).toBe(-1);
    expect(urgencySwapDelta(1, 15, rows)).toBeNull();
  });

  it('swaps downward once the pointer crosses the row below', () => {
    expect(urgencySwapDelta(1, 52, rows)).toBe(1);
    expect(urgencySwapDelta(1, 25, rows)).toBeNull();
  });

  it('does not swap past the ends of the list', () => {
    expect(urgencySwapDelta(0, -10, rows)).toBeNull();
    expect(urgencySwapDelta(2, 80, rows)).toBeNull();
  });

  it('swaps distinct urgencies when the neighbor is not in an equal block', () => {
    const move = planUrgencyMove(tickets(1, 5, 8), 2, -1);
    expect(mapOf(move?.patches ?? [])).toEqual({ C: 5, B: 8 });
    expect(move?.clearSecondary).toBe(false);
  });

  it('joins a block of equal urgencies at that value and leaves the replaced ticket', () => {
    const block = tickets(5, 5, 5, 9);
    const move = planUrgencyMove(block, 3, -1);
    expect(mapOf(move?.patches ?? [])).toEqual({ D: 5 });
    expect(move?.orderIds).toEqual(['A', 'B', 'D', 'C']);
    expect(move?.clearSecondary).toBe(true);
  });

  it('keeps both tickets at the block value when moving inside it', () => {
    const move = planUrgencyMove(tickets(5, 5, 5), 2, -1);
    expect(move?.patches).toEqual([]);
    expect(move?.orderIds).toEqual(['A', 'C', 'B']);
    expect(move?.clearSecondary).toBe(true);
  });

  it('moves down into an equal block the same way', () => {
    const move = planUrgencyMove(tickets(9, 5, 5), 0, 1);
    expect(mapOf(move?.patches ?? [])).toEqual({ A: 5 });
    expect(move?.orderIds).toEqual(['B', 'A', 'C']);
    expect(move?.clearSecondary).toBe(true);
  });
});
