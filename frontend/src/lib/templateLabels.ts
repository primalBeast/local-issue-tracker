import type { FieldDef } from './api';
import { displayRowNumber, displayWidth, lineOf, slotOf } from './templatePlacement';

export const PROJECT_FIELDS_LABEL = "This project's fields";
export const BUILTIN_LABEL = 'Built-in (read-only)';
export const DEFAULT_BADGE = 'Default for new projects';

const ONES = ['', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth'];
const TEENS = [
  'tenth',
  'eleventh',
  'twelfth',
  'thirteenth',
  'fourteenth',
  'fifteenth',
  'sixteenth',
  'seventeenth',
  'eighteenth',
  'nineteenth',
];

export function ordinalWord(n: number): string {
  if (n <= 0) return String(n);
  if (n < 10) return ONES[n] || `${n}th`;
  if (n < 20) return TEENS[n - 10] || `${n}th`;
  return `position ${n}`;
}

export function widthPhrase(percent: number): string {
  const p = Math.round(percent);
  if (p === 100) return 'full width';
  if (p === 50) return 'half width';
  if (p === 25) return 'quarter width';
  if (p === 33 || p === 34) return 'third width';
  return `${p}% wide`;
}

export function placementPhrase(f: FieldDef, fields: FieldDef[]): string {
  const row = displayRowNumber(fields, lineOf(f));
  return `Row ${row} · ${ordinalWord(slotOf(f))} · ${widthPhrase(displayWidth(f, fields))}`;
}

export function formatVisibleWhen(vw: FieldDef['visible_when'], fields: FieldDef[]): string | null {
  if (!vw?.field) return null;
  const name = fields.find((f) => f.id === vw.field)?.label || vw.field;
  if (Object.prototype.hasOwnProperty.call(vw, 'equals')) {
    if (vw.equals === true) return `until ${name} is checked`;
    if (vw.equals === false) return `until ${name} is off`;
    return `until ${name} is ${String(vw.equals)}`;
  }
  if (Object.prototype.hasOwnProperty.call(vw, 'not_equals')) {
    if (vw.not_equals === true) return `unless ${name} is checked`;
    if (vw.not_equals === false) return `unless ${name} is off`;
    return `unless ${name} is ${String(vw.not_equals)}`;
  }
  if (typeof vw.starts_with === 'string') {
    return `when ${name} starts with ${vw.starts_with}`;
  }
  return null;
}

const TITLE_EDITOR_IDS = new Set(['ticket_key', 'title', 'alternate_ticket']);

export function fieldVisibilityHint(f: FieldDef, fields: FieldDef[]): string | null {
  if (TITLE_EDITOR_IDS.has(f.id)) return 'until title is expanded';
  return formatVisibleWhen(f.visible_when, fields);
}

export function lineVisibilityHint(lineFields: FieldDef[], all: FieldDef[]): string | null {
  const hints = lineFields.map((f) => fieldVisibilityHint(f, all)).filter((h): h is string => Boolean(h));
  if (!hints.length) return null;
  const unique = [...new Set(hints)];
  const allHave = hints.length === lineFields.length;
  const text = unique.join(' · ');
  return allHave ? text : `some ${text}`;
}
