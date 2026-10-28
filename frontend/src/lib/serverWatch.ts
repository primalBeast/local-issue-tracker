/** How long the server can stay quiet before the app restarts it. */
export const AUTO_RESTART_AFTER_MS = 15_000;

/** True once the server has been down long enough to restart on its own. */
export function shouldAutoRestart(
  downSince: number,
  now: number,
  restarting: boolean,
  waitMs = AUTO_RESTART_AFTER_MS
): boolean {
  if (restarting || !(downSince > 0)) return false;
  if (!Number.isFinite(now) || !Number.isFinite(downSince)) return false;
  return now - downSince >= waitMs;
}
