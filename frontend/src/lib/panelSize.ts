import type { FieldDef } from './api';
import type { FieldRow } from './fieldLayout';

/** Visible text lines inside the Notes editor on a new item panel. */
export const NOTES_MIN_LINES = 3;
export const NOTES_LINE_PX = 23;
export const NOTES_EDITOR_PAD_PX = 16;
export const NOTES_TOOLBAR_PX = 34;
export const NOTES_LABEL_PX = 18;
export const PANEL_HEADER_PX = 41;
/** Extra header height while the ticket-number/description editor is open. */
export const HEADER_TITLE_EDITOR_PX = 88;
export const PANEL_BODY_PAD_PX = 22;
export const FIELD_ROW_EST_PX = 62;

export function notesEditorMinPx(lines = NOTES_MIN_LINES): number {
  return NOTES_EDITOR_PAD_PX + NOTES_LINE_PX * lines;
}

export function notesBlockMinPx(lines = NOTES_MIN_LINES): number {
  return NOTES_LABEL_PX + NOTES_TOOLBAR_PX + notesEditorMinPx(lines);
}

export function isNotesFillRow(row: FieldRow): boolean {
  return row.fields.some((f) => f.id === 'notes' || f.type === 'richtext');
}

/** Minimum item-panel height so Notes shows at least `lines` of the editor. */
export function minItemPanelHeight(rows: FieldRow[], lines = NOTES_MIN_LINES): number {
  let above = 0;
  let hasNotes = false;
  for (const row of rows) {
    if (isNotesFillRow(row)) {
      hasNotes = true;
      continue;
    }
    above += 1;
  }
  const notes = hasNotes ? notesBlockMinPx(lines) : 0;
  return PANEL_HEADER_PX + PANEL_BODY_PAD_PX + above * FIELD_ROW_EST_PX + notes;
}

export function isFillField(def: FieldDef): boolean {
  return def.id === 'notes' || def.type === 'richtext';
}
