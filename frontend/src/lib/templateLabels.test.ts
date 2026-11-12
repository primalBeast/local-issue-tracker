import { describe, expect, it } from 'vitest';
import type { FieldDef } from './api';
import {
  BUILTIN_LABEL,
  DEFAULT_BADGE,
  PROJECT_FIELDS_LABEL,
  ordinalWord,
  placementPhrase,
  widthPhrase,
} from './templateLabels';
import { dialogTitle, listEntries, type TemplateInfo } from './templateListModel';

function f(id: string, order: number | string, width?: number): FieldDef {
  return { id, label: id, type: 'text', order, width };
}

describe('plain names', () => {
  it('uses This project / Built-in labels and a default badge', () => {
    expect(PROJECT_FIELDS_LABEL).toBe("This project's fields");
    expect(BUILTIN_LABEL).toBe('Built-in (read-only)');
    expect(DEFAULT_BADGE).toBe('Default for new projects');
    const templates: TemplateInfo[] = [
      { id: 'issue-tracker', name: 'Issue tracker', origin: 'shipped', editable: false, is_default: true },
      { id: 'mine', name: 'Mine', origin: 'user', editable: true, is_default: false },
    ];
    const entries = listEntries(templates, 'project');
    expect(entries.project.label).toBe(PROJECT_FIELDS_LABEL);
    expect(entries.builtin?.kind).toBe('builtin');
    expect(entries.builtin?.label).toBe(BUILTIN_LABEL);
    expect(entries.builtin && entries.builtin.badge).toBe(DEFAULT_BADGE);
    expect(entries.saved.map((t) => t.label)).toEqual(['Mine']);
    expect(dialogTitle('project', templates, 'Alpha')).toBe(PROJECT_FIELDS_LABEL);
    expect(dialogTitle('mine', templates, 'Alpha')).toBe('Mine');
  });

  it('describes placement in plain words instead of LINE 10 / 1st · 25%', () => {
    const fields = [f('a', 10, 100), f('b', '30a', 25), f('c', '30b', 75)];
    expect(placementPhrase(fields[1]!, fields)).toBe('Row 2 · first · quarter width');
    expect(placementPhrase(fields[2]!, fields)).toBe('Row 2 · second · 75% wide');
    expect(widthPhrase(50)).toBe('half width');
    expect(ordinalWord(3)).toBe('third');
  });
});
