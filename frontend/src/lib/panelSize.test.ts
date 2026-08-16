import { describe, expect, it } from 'vitest';
import type { FieldDef } from './api';
import { groupFieldsByRow } from './fieldLayout';
import { minItemPanelHeight, notesEditorMinPx, NOTES_MIN_LINES } from './panelSize';

function f(id: string, order: number | string, type = 'text'): FieldDef {
  return { id, label: id, type, order };
}

describe('panelSize', () => {
  it('reserves three lines plus editor chrome for Notes', () => {
    expect(notesEditorMinPx()).toBeGreaterThanOrEqual(NOTES_MIN_LINES * 16);
  });

  it('is taller when there are more fields above Notes', () => {
    const few = groupFieldsByRow([f('title', 10), f('notes', 20, 'richtext')]);
    const many = groupFieldsByRow([
      f('ticket_key', 10),
      f('title', 20),
      f('priority', '30a'),
      f('state', '30b'),
      f('notes', 60, 'richtext'),
    ]);
    expect(minItemPanelHeight(many)).toBeGreaterThan(minItemPanelHeight(few));
  });
});
