/** Notes date: "m/d" with no leading zeros. */
export function formatNoteDate(d: Date = new Date()): string {
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** Notes date stamp: "m/d - " with no leading zeros. */
export function formatNoteDateStamp(d: Date = new Date()): string {
  return `${formatNoteDate(d)} - `;
}

export type NoteDateHit = { start: number; end: number };

/**
 * A `m/d` or `mm/dd` span (month 1–12, day 1–31) that the caret is inside
 * or immediately after. Does not treat `8/17/2026` as a date.
 */
export function findNoteDateAround(text: string, caret: number): NoteDateHit | null {
  const pos = Math.max(0, Math.min(text.length, caret | 0));
  const re = /(?<![\d/])(\d{1,2})\/(\d{1,2})(?![\d/])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const month = Number(m[1]);
    const day = Number(m[2]);
    if (month < 1 || month > 12 || day < 1 || day > 31) continue;
    const start = m.index;
    const end = start + m[0].length;
    if (pos >= start && pos <= end) return { start, end };
  }
  return null;
}
