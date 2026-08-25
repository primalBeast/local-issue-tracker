export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return '—';
  const s = Math.floor(seconds);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export function formatWaitingDays(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return '0 days';
  const days = Math.floor(seconds / 86400);
  return days === 1 ? '1 day' : `${days} days`;
}

export function todayLocalDate(now = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Select choices plus the current value if it is not already in the list. */
export function waitingNameChoices(options: string[] | undefined, current: unknown): string[] {
  const opts = [...(options ?? [])];
  const cur = String(current ?? '').trim();
  if (cur && !opts.includes(cur)) opts.push(cur);
  return opts;
}

export function isItemWaiting(item: {
  fields?: Record<string, unknown>;
  waiting?: { is_waiting?: boolean } | null;
}): boolean {
  return Boolean(item.fields?.waiting) || Boolean(item.waiting?.is_waiting);
}

export function liveSeconds(startedAt: string | null | undefined, nowMs = Date.now()): number | null {
  if (!startedAt) return null;
  const t = Date.parse(startedAt);
  if (Number.isNaN(t)) return null;
  return Math.max(0, (nowMs - t) / 1000);
}
