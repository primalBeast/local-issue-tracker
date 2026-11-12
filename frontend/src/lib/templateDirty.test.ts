import { describe, expect, it } from 'vitest';
import type { FieldDef, FieldsDoc } from './api';
import {
  editorIsDirty,
  extraFromDoc,
  normalizeLoadedFields,
  saveEnabled,
  savePayload,
  snapshotOf,
} from './templateDirty';
import { columnVisible, defaultColumnOrder } from './listColumns';
import { patchField } from './templateFields';

function field(id: string, extra: Partial<FieldDef> = {}): FieldDef {
  return { id, label: id, type: 'text', order: 10, show_in_list: true, ...extra };
}

const loaded: FieldsDoc = {
  version: 1,
  fields: [
    field('ticket_key', { label: 'Ticket number', order: 10, show_in_list: true }),
    field('title', { label: 'Description', order: 20, show_in_list: true }),
    field('notes', { label: 'Notes', type: 'richtext', order: 60, show_in_list: false }),
  ],
  system_fields: { waiting_total_seconds: { computed: true } },
};

describe('dirty snapshot', () => {
  it('opening and saving with no edits keeps a byte-identical payload', () => {
    const fields = normalizeLoadedFields(loaded.fields);
    const extra = extraFromDoc(loaded);
    const snap = snapshotOf(fields, extra, loaded.version);
    const payload = savePayload(fields, extra, loaded.version);
    expect(JSON.stringify(payload)).toBe(snap);
    expect(editorIsDirty(fields, extra, loaded.version, snap)).toBe(false);
    expect(saveEnabled(true, false, false)).toBe(false);
  });

  it('an edit dirties, reverting it cleans, and Save stays off until dirty', () => {
    const fields = normalizeLoadedFields(loaded.fields);
    const extra = extraFromDoc(loaded);
    const snap = snapshotOf(fields, extra, loaded.version);
    const edited = patchField(fields, 'title', { label: 'Renamed' });
    expect(editorIsDirty(edited, extra, loaded.version, snap)).toBe(true);
    expect(saveEnabled(true, true, false)).toBe(true);
    expect(saveEnabled(true, true, true)).toBe(false);
    expect(saveEnabled(false, true, false)).toBe(false);
    const reverted = patchField(edited, 'title', { label: 'Description' });
    expect(editorIsDirty(reverted, extra, loaded.version, snap)).toBe(false);
    expect(saveEnabled(true, false, false)).toBe(false);
  });

  it('preserves show_in_list through save and leaves All Items columns unchanged', () => {
    const fields = normalizeLoadedFields(loaded.fields);
    const extra = extraFromDoc(loaded);
    const renamed = patchField(fields, 'title', { label: 'Renamed' });
    const payload = savePayload(renamed, extra, loaded.version);
    expect(payload.fields.find((f) => f.id === 'ticket_key')?.show_in_list).toBe(true);
    expect(payload.fields.find((f) => f.id === 'notes')?.show_in_list).toBe(false);
    expect(defaultColumnOrder(payload.fields, true)).toEqual(defaultColumnOrder(loaded.fields, true));
    expect(columnVisible(payload.fields.find((f) => f.id === 'notes')!, undefined)).toBe(false);
    expect(columnVisible(payload.fields.find((f) => f.id === 'ticket_key')!, undefined)).toBe(true);
  });
});
