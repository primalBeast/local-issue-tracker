/** Build a launchable ticket URL from a project prefix + ticket key, or null. */
export function ticketHref(
  prefix: string | null | undefined,
  ticketKey: string | null | undefined
): string | null {
  const p = String(prefix ?? '').trim();
  const k = String(ticketKey ?? '').trim();
  if (!p || !k) return null;
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
