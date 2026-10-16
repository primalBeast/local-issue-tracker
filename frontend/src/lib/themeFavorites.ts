import type { ThemeMenuEntry } from './themes';

export type ThemeFavorite = { id: string; pulse: number };

export type ThemeMenuRow = ThemeMenuEntry & { key: string };

const ID_RE = /^[a-z0-9_-]{1,40}$/;

/** Full glow cycle. Half of this is about two seconds, brightest to darkest. */
export function favoritePulsePeriod(rand: () => number = Math.random): number {
  const half = 1.7 + rand() * 0.6;
  return Math.round(half * 2 * 100) / 100;
}

export function parseFavorites(raw: unknown): ThemeFavorite[] {
  if (!Array.isArray(raw)) return [];
  const out: ThemeFavorite[] = [];
  const seen = new Set<string>();
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const id = (item as { id?: unknown }).id;
    if (typeof id !== 'string' || !ID_RE.test(id) || seen.has(id)) continue;
    const pulseRaw = (item as { pulse?: unknown }).pulse;
    const pulseNum = typeof pulseRaw === 'number' ? pulseRaw : Number(pulseRaw);
    const pulse = Number.isFinite(pulseNum) ? Math.min(8, Math.max(2, pulseNum)) : 4;
    seen.add(id);
    out.push({ id, pulse });
    if (out.length >= 80) break;
  }
  return out;
}

export function toggleFavorite(
  list: ThemeFavorite[],
  id: string,
  rand: () => number = Math.random
): ThemeFavorite[] {
  if (list.some((f) => f.id === id)) return list.filter((f) => f.id !== id);
  return [...list, { id, pulse: favoritePulsePeriod(rand) }];
}

/** Favourites first, then the normal menu. A theme can appear in both. */
export function themeMenuRows(menu: ThemeMenuEntry[], favorites: ThemeFavorite[]): ThemeMenuRow[] {
  const byId = new Map(menu.map((entry) => [entry.theme.id, entry]));
  const top: ThemeMenuRow[] = [];
  const seen = new Set<string>();
  for (const fav of favorites) {
    if (seen.has(fav.id)) continue;
    const entry = byId.get(fav.id);
    if (!entry) continue;
    seen.add(fav.id);
    top.push({ ...entry, group: 'Favourites', key: `fav:${fav.id}` });
  }
  return [...top, ...menu.map((entry) => ({ ...entry, key: `all:${entry.theme.id}` }))];
}

/** Arrow-key order: each favourite once, then the themes that are not favourites. */
export function themeNavIds(menu: ThemeMenuEntry[], favorites: ThemeFavorite[]): string[] {
  const known = new Set(menu.map((entry) => entry.theme.id));
  const favIds: string[] = [];
  const seen = new Set<string>();
  for (const fav of favorites) {
    if (!known.has(fav.id) || seen.has(fav.id)) continue;
    seen.add(fav.id);
    favIds.push(fav.id);
  }
  return [...favIds, ...menu.map((entry) => entry.theme.id).filter((id) => !seen.has(id))];
}
