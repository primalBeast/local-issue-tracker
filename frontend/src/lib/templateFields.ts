import type { FieldDef } from './api';
import { lineOf } from './templatePlacement';

export const CONTROL_TYPES = [
  'text',
  'textarea',
  'richtext',
  'select',
  'multiselect',
  'checkbox',
  'number',
  'date',
  'datetime',
  'url',
] as const;

export const RESERVED = new Set([
  'ticket_key',
  'title',
  'alternate_ticket',
  'waiting',
  'waiting_for',
  'waiting_since',
  'notes',
]);

export const TITLE_EDITOR_IDS = new Set(['ticket_key', 'title', 'alternate_ticket']);

export function slugify(label: string): string {
  const s = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 40);
  return s || `field_${Date.now().toString(36)}`;
}

export function uniqueId(fields: FieldDef[], base: string): string {
  let id = base;
  let n = 2;
  const used = new Set(fields.map((f) => f.id));
  while (used.has(id)) {
    id = `${base}_${n}`;
    n += 1;
  }
  return id;
}

export function addField(fields: FieldDef[]): FieldDef[] {
  const rows = fields.map((f) => lineOf(f)).filter((n) => Number.isFinite(n));
  const order = (rows.length ? Math.max(...rows) : 0) + 10;
  return [
    ...fields,
    {
      id: uniqueId(fields, 'new_field'),
      label: 'New field',
      type: 'text',
      required: false,
      order,
      default: '',
      show_in_list: false,
    },
  ];
}

export function removeField(fields: FieldDef[], id: string): FieldDef[] {
  if (!id || RESERVED.has(id)) return fields;
  return fields.filter((f) => f.id !== id);
}

export function patchField(fields: FieldDef[], id: string, patch: Partial<FieldDef>): FieldDef[] {
  const i = fields.findIndex((f) => f.id === id);
  if (i < 0) return fields;
  return fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f));
}

export function setFieldType(fields: FieldDef[], id: string, type: string): FieldDef[] {
  const i = fields.findIndex((f) => f.id === id);
  if (i < 0) return fields;
  const f = { ...fields[i], type };
  if ((type === 'select' || type === 'multiselect') && !f.options?.length) f.options = ['Option 1'];
  return fields.map((x, idx) => (idx === i ? f : x));
}

export function setFieldOptions(fields: FieldDef[], id: string, text: string): FieldDef[] {
  const options = text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  return patchField(fields, id, { options });
}

export function sampleValue(f: FieldDef): unknown {
  if (f.default !== undefined && f.default !== '') return f.default;
  if (f.type === 'select' && f.options?.[0]) return f.options[0];
  if (f.type === 'multiselect') return [];
  if (f.type === 'checkbox') return false;
  if (f.type === 'number') return 5;
  if (f.type === 'date') return '2026-08-23';
  if (f.type === 'datetime') return '2026-08-23T12:00';
  if (f.type === 'richtext') return { type: 'doc', content: [] };
  if (f.id === 'ticket_key') return 'PROJ-1';
  if (f.id === 'title') return 'Example ticket';
  return '';
}
