/**
 * Parse a number-field text box.
 *
 * Blank or whitespace clears the field (`null`), including a required rank.
 * A finite number, including 0, is that number.
 * Anything else (`abc`, `NaN`) is `undefined`: callers keep the stored value.
 * Optional min/max reject out-of-range numbers the same way.
 */
export function parseNumberInput(
  raw: string,
  bounds?: { min?: unknown; max?: unknown }
): number | null | undefined {
  if (raw.trim() === '') return null;
  const n = Number(raw.trim());
  if (!Number.isFinite(n)) return undefined;
  if (typeof bounds?.min === 'number' && n < bounds.min) return undefined;
  if (typeof bounds?.max === 'number' && n > bounds.max) return undefined;
  return n;
}
