import type { FieldDef, FieldsDoc } from './api';

export function toPlain<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function cloneFields(fields: FieldDef[]): FieldDef[] {
  return toPlain(fields);
}

/** Rest of a loaded fields doc after pulling fields + version into editor state. */
export function extraFromDoc(doc: FieldsDoc): Record<string, unknown> {
  const extra = { ...(doc as unknown as Record<string, unknown>) };
  delete extra.fields;
  delete extra.version;
  return extra;
}

export function savePayload(
  fields: FieldDef[],
  extra: Record<string, unknown>,
  version: number
): FieldsDoc {
  const rest = toPlain(extra) as Record<string, unknown>;
  delete rest.fields;
  delete rest.version;
  return { ...rest, version, fields: toPlain(fields) } as FieldsDoc;
}

export function snapshotOf(fields: FieldDef[], extra: Record<string, unknown>, version: number): string {
  return JSON.stringify(savePayload(fields, extra, version));
}

export function isDirty(current: string, snapshot: string): boolean {
  return current !== snapshot;
}

export function editorIsDirty(
  fields: FieldDef[],
  extra: Record<string, unknown>,
  version: number,
  snapshot: string
): boolean {
  return isDirty(snapshotOf(fields, extra, version), snapshot);
}

export function saveEnabled(canSave: boolean, dirty: boolean, busy: boolean): boolean {
  return canSave && dirty && !busy;
}

export function normalizeLoadedFields(fields: FieldDef[]): FieldDef[] {
  return fields.map((f) => {
    const copy = { ...f, options: f.options ? [...f.options] : f.options };
    if (copy.id === 'ticket_key' && copy.label === 'Ticket Key') copy.label = 'Ticket number';
    if (copy.id === 'title' && copy.label === 'Title') copy.label = 'Description';
    return copy;
  });
}
