/** Gap that means the machine slept, not a late timer. */
export const WAKE_GAP_MS = 8_000;

/** True when wall-clock time jumped forward across a sleep. */
export function wokeFromSleep(lastMs: number, nowMs: number, gapMs = WAKE_GAP_MS): boolean {
  if (!Number.isFinite(lastMs) || !Number.isFinite(nowMs)) return false;
  return nowMs - lastMs > gapMs;
}
