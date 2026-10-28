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

/**
 * The value to store while a number box is being typed.
 * `undefined` means the draft is incomplete or unchanged, so leave the field alone.
 */
export function liveNumberValue(
  draft: string,
  original: unknown,
  bounds?: { min?: unknown; max?: unknown; required?: boolean }
): number | null | undefined {
  const parsed = parseNumberInput(draft, bounds);
  if (parsed === undefined) return undefined;
  const blank = original == null || original === '';
  if (parsed === null) return blank ? undefined : null;
  if (blank || Number(original) !== parsed) return parsed;
  return undefined;
}
