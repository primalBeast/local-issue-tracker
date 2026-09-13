import { urlTail } from './urlTicket';

/** Display form of a ticket key: last path segment when the value is a full URL. */
export function ticketNumberLabel(raw: string | null | undefined): string {
  const s = String(raw ?? '').trim();
  if (!s) return '';
  if (launchableHref(s)) return urlTail(s) || s;
  return s;
}

/** Build a launchable ticket URL. A full http(s) ticket key is used as-is; otherwise prefix + key. */
export function ticketHref(
  prefix: string | null | undefined,
  ticketKey: string | null | undefined
): string | null {
  const k = String(ticketKey ?? '').trim();
  if (!k) return null;
  const direct = launchableHref(k);
  if (direct) return direct;
  const p = String(prefix ?? '').trim();
  if (!p) return null;
  try {
    const base = new URL(p);
    if (base.protocol !== 'http:' && base.protocol !== 'https:') return null;
    if (!base.hostname) return null;
    const url = new URL(p + k);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!url.hostname) return null;
    return url.href;
  } catch {
    return null;
  }
}

/** Validate a complete URL for launching (http/https only). */
export function launchableHref(raw: string | null | undefined): string | null {
  const s = String(raw ?? '').trim();
  if (!s) return null;
  try {
    const url = new URL(s);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!url.hostname) return null;
    return url.href;
  } catch {
    return null;
  }
}

/** Pair of launchable ticket URLs for a side-by-side Edge split. */
export function splitTicketUrls(
  masterHref: string | null | undefined,
  externalHref: string | null | undefined
): { left: string; right: string } | null {
  const left = launchableHref(masterHref);
  const right = launchableHref(externalHref);
  if (!left || !right) return null;
  return { left, right };
}
