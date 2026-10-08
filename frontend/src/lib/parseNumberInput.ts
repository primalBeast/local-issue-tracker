/**
 * Parse a number-field text box.
 *
 * Blank or whitespace clears an optional field (`null`).
 * A blank required field is `undefined` (keep the stored value), same as
 * invalid text (`abc`, `NaN`) and numbers outside min/max.
 * A finite number, including 0, is that number.
 */
export function parseNumberInput(
  raw: string,
  bounds?: { min?: unknown; max?: unknown; required?: boolean }
): number | null | undefined {
  if (raw.trim() === '') return bounds?.required ? undefined : null;
  const n = Number(raw.trim());
  if (!Number.isFinite(n)) return undefined;
  if (typeof bounds?.min === 'number' && n < bounds.min) return undefined;
  if (typeof bounds?.max === 'number' && n > bounds.max) return undefined;
  return n;
}
