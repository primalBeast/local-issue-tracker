const DEFAULT_PREFIX = 'NEW-';

export function normalizeTicketPrefix(raw: string | null | undefined): string {
  let p = String(raw ?? '').trim();
  p = p.replace(/[^A-Za-z0-9._-]+/g, '');
  if (!p) return DEFAULT_PREFIX;
  if (!/[.\-_]$/.test(p)) p += '-';
  return p.slice(0, 32);
}

export function nextTicketKey(existingKeys: string[], prefix: string | null | undefined): string {
  const p = normalizeTicketPrefix(prefix);
  let max = 0;
  for (const key of existingKeys) {
    if (!key.startsWith(p)) continue;
    const rest = key.slice(p.length);
    if (/^\d+$/.test(rest)) max = Math.max(max, Number(rest));
  }
  return `${p}${max + 1}`;
}

export function slugFromName(name: string): string {
  let s = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 62);
  if (!s || !/^[a-z0-9]/.test(s)) return 'project';
  return s;
}

export function uniqueSlug(base: string, existing: string[]): string {
  const taken = new Set(existing);
  if (!taken.has(base)) return base;
  for (let i = 2; i < 1000; i++) {
    const candidate = `${base.slice(0, 60)}-${i}`.slice(0, 63);
    if (!taken.has(candidate)) return candidate;
  }
  return `${base.slice(0, 54)}-${Date.now().toString(36)}`.slice(0, 63);
}
