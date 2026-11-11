import { describe, expect, it } from 'vitest';
import appSource from '../App.svelte?raw';
import menuSource from './ProjectMenu.svelte?raw';
import settingsSource from './ProjectSettingsDialog.svelte?raw';
import { pickerItemState, TAKEN_TITLE } from './projectClaims';
import {
  initialNewProjectDraft,
  menuFitsWithoutScrolling,
  moveMenuFocus,
  newProjectCreateArgs,
  projectMenuEntries,
  resolveSettingsClose,
  rootFocusableIndexes,
  settingsDraftFromProject,
  switchFocusableIndexes,
  switchProjectMenu,
  templateOptionLabel,
  URL_PREFIX_HINT,
  URL_PREFIX_PLACEHOLDER,
} from './projectMenu';

describe('project menu model', () => {
  it('lists items in spec order, including both dividers', () => {
    expect(projectMenuEntries()).toEqual([
      { kind: 'item', id: 'settings', label: 'Project settings…' },
      { kind: 'item', id: 'switch', label: 'Switch project', submenu: true },
      { kind: 'item', id: 'new', label: 'New project…' },
      { kind: 'item', id: 'templates', label: 'Templates…' },
      { kind: 'separator' },
      { kind: 'item', id: 'open-folder', label: 'Open data folder' },
      { kind: 'separator' },
      { kind: 'item', id: 'reload', label: 'Reload (F5)' },
      { kind: 'item', id: 'release-notes', label: 'Release notes' },
    ]);
    const focusable = rootFocusableIndexes(projectMenuEntries());
    expect(moveMenuFocus(focusable, focusable[0] ?? 0, 'Home')).toBe(focusable[0]);
    expect(moveMenuFocus(focusable, focusable[0] ?? 0, 'End')).toBe(focusable[focusable.length - 1]);
    expect(moveMenuFocus(focusable, focusable[0] ?? 0, 'ArrowUp')).toBe(focusable[focusable.length - 1]);
    expect(moveMenuFocus(focusable, focusable[focusable.length - 1] ?? 0, 'ArrowDown')).toBe(
      focusable[0]
    );
  });

  it('marks the current project, disables a locked one with the picker tooltip, and ends with Close project', () => {
    expect(TAKEN_TITLE).toBe('Already open in another window');
    const entries = switchProjectMenu(
      [
        { slug: 'alpha', name: 'Alpha' },
        { slug: 'beta', name: 'Beta' },
        { slug: 'gamma', name: 'Gamma' },
      ],
      'beta',
      (slug) => pickerItemState({ alpha: 'other-window' }, 'this-window', slug, 'beta')
    );
    expect(entries).toEqual([
      {
        kind: 'project',
        slug: 'alpha',
        name: 'Alpha',
        current: false,
        disabled: true,
        title: 'Already open in another window',
      },
      {
        kind: 'project',
        slug: 'beta',
        name: 'Beta',
        current: true,
        disabled: false,
        title: undefined,
      },
      {
        kind: 'project',
        slug: 'gamma',
        name: 'Gamma',
        current: false,
        disabled: false,
        title: undefined,
      },
      { kind: 'separator' },
      { kind: 'close', label: 'Close project' },
    ]);
    expect(entries.at(-2)).toEqual({ kind: 'separator' });
    expect(entries.at(-1)).toEqual({ kind: 'close', label: 'Close project' });
    expect(switchFocusableIndexes(entries)).toEqual([1, 2, 4]);
    expect(menuSource).toContain("entry.current ? '✓'");
    expect(menuSource).toContain('disabled={entry.disabled}');
    expect(menuSource).toContain('title={entry.title}');
    expect(menuSource).toContain('Close project');
    expect(menuSource).toContain('pickerItemState');
    expect(menuSource).toContain('role="menu"');
    expect(menuSource).toContain('role="menuitem"');
  });

  it('fits every row on a 900px-tall window without scrolling', () => {
    expect(menuFitsWithoutScrolling(900)).toBe(true);
    expect(projectMenuEntries()).toHaveLength(9);
  });
});

describe('project settings draft', () => {
  const saved = settingsDraftFromProject({
    name: 'Alpha',
    ticket_prefix: 'AL-',
    url_prefix: 'https://old.example/browse/',
  });
  const edited = { ...saved, name: 'Renamed', ticketPrefix: 'RN-', urlPrefix: 'https://new.example/' };

  it('Save persists the draft and Cancel or Escape discards it', () => {
    expect(resolveSettingsClose(saved, edited, 'save')).toEqual({
      saved: edited,
      persist: edited,
    });
    for (const reason of ['cancel', 'escape'] as const) {
      const result = resolveSettingsClose(saved, edited, reason);
      expect(result.persist).toBeNull();
      expect(result.saved).toEqual(saved);
      expect(result.saved.name).toBe('Alpha');
    }
    expect(URL_PREFIX_PLACEHOLDER).toBe('https://jira.example.com/browse/');
    expect(URL_PREFIX_HINT).toBe('Ticket keys link to this URL plus the key.');
    expect(settingsSource).toContain('URL_PREFIX_PLACEHOLDER');
    expect(settingsSource).toContain('URL_PREFIX_HINT');
    expect(settingsSource).toContain('>Cancel<');
    expect(settingsSource).toContain('>Save<');
    expect(settingsSource).not.toContain('Templates');
  });

  it('editing the name then opening Templates does not save', () => {
    const result = resolveSettingsClose(saved, edited, 'templates');
    expect(result.persist).toBeNull();
    expect(result.saved).toEqual(saved);
    expect(result.saved.name).toBe('Alpha');

    expect(appSource).not.toContain('closeProjectEditor');
    expect(appSource).not.toContain('projectEditor');
    const start = appSource.indexOf('function openTemplateEditor');
    expect(start).toBeGreaterThanOrEqual(0);
    const next = appSource.indexOf('\n  function ', start + 'function openTemplateEditor'.length);
    const body = appSource.slice(start, next === -1 ? undefined : next);
    expect(body).toContain('templateEditorOpen = true');
    expect(body).not.toContain('persistProjectMeta');
    expect(body).not.toContain('closeProjectEditor');

    const templatesAt = appSource.indexOf("id === 'templates'");
    expect(templatesAt).toBeGreaterThanOrEqual(0);
    const region = appSource.slice(templatesAt, templatesAt + 280);
    expect(region).toContain('openTemplateEditor');
    expect(region).not.toContain('persistProjectMeta');
    expect(region).not.toContain('closeProjectEditor');
  });
});

describe('new project draft', () => {
  it('uses the same template labels and refuses a blank name', () => {
    expect(templateOptionLabel({ id: 'issue-tracker', name: 'Issue tracker', is_default: true })).toBe(
      'Issue tracker (default)'
    );
    expect(templateOptionLabel({ id: 'blank', name: 'Blank', is_default: false })).toBe('Blank');
    const draft = initialNewProjectDraft('issue-tracker');
    expect(draft).toEqual({ name: '', ticketPrefix: 'NEW-', templateId: 'issue-tracker' });
    expect(newProjectCreateArgs(draft)).toBeNull();
    expect(newProjectCreateArgs({ ...draft, name: '  Side quest  ' })).toEqual({
      name: 'Side quest',
      ticketPrefix: 'NEW-',
      templateId: 'issue-tracker',
    });
  });
});
