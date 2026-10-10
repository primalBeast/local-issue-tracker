import type { Item } from './api';

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const STALE_MS = 14 * 24 * 60 * 60 * 1000;

export function isDoneState(state: unknown): boolean {
  return String(state ?? '') === 'Done';
}

/** Due date is before today and the ticket is not Done. */
export function isOverdue(
  item: { fields: Record<string, unknown> },
  today: string
): boolean {
  if (isDoneState(item.fields.state)) return false;
  const due = String(item.fields.due_on ?? '');
  return ISO_DATE.test(due) && ISO_DATE.test(today) && due < today;
}

/** Not updated within `days` (default 14) and not Done. */
export function isStale(
  item: { fields: Record<string, unknown>; updated_at?: string | null },
  now = Date.now(),
  days = 14
): boolean {
  if (isDoneState(item.fields.state)) return false;
  const raw = item.updated_at;
  if (!raw) return false;
  const stamp = Date.parse(raw);
  if (!Number.isFinite(stamp)) return false;
  return now - stamp > days * 24 * 60 * 60 * 1000;
}

export function itemSummaryText(item: Item): string {
  const fields = item.fields || {};
  const lines = [
    String(fields.ticket_key ?? '').trim() || 'Untitled',
    String(fields.title ?? '').trim(),
  ].filter(Boolean);
  const state = String(fields.state ?? '').trim();
  if (state) lines.push(`State: ${state}`);
  if (fields.priority != null && fields.priority !== '') lines.push(`Priority: ${fields.priority}`);
  if (fields.urgency != null && fields.urgency !== '') lines.push(`Urgency: ${fields.urgency}`);
  const due = String(fields.due_on ?? '').trim();
  if (due) lines.push(`Due: ${due}`);
  if (fields.pinned === true) lines.push('Pinned');
  if (item.waiting?.is_waiting) {
    const who = String(fields.waiting_for ?? '').trim();
    lines.push(who ? `Waiting for ${who}` : 'Waiting');
  }
  return lines.join('\n');
}

export { STALE_MS };
