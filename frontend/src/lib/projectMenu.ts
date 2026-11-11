import type { PickerItemState } from './projectClaims';

/** Top-level project menu. Dividers are their own entries so order is testable. */
export type ProjectMenuItemId =
  | 'settings'
  | 'switch'
  | 'new'
  | 'templates'
  | 'open-folder'
  | 'reload'
  | 'release-notes';

export type ProjectMenuActionId = Exclude<ProjectMenuItemId, 'switch'>;

export type MenuEntry =
  | { kind: 'separator' }
  | { kind: 'item'; id: ProjectMenuItemId; label: string; submenu?: boolean };

/**
 * Compact row budget for the project menu (matches the CSS row).
 * At a 900px window the whole list must sit on screen without scrolling.
 * Order: Project settings…, Switch project ▸, New project…, Templates…,
 * divider, Open data folder, divider, Reload (F5), Release notes.
 */
export const MENU_ROW_BUDGET_PX = 32;
export const MENU_CHROME_PX = 16;
export const MENU_TOP_OFFSET_PX = 48 + 8;

export function projectMenuBlockHeight(entries: readonly MenuEntry[] = projectMenuEntries()): number {
  return MENU_CHROME_PX + entries.length * MENU_ROW_BUDGET_PX;
}

export function menuFitsWithoutScrolling(windowHeight: number, topOffset = MENU_TOP_OFFSET_PX): boolean {
  const height = projectMenuBlockHeight();
  return height <= windowHeight - topOffset && height <= windowHeight;
}

export function projectMenuEntries(): MenuEntry[] {
  return [
    { kind: 'item', id: 'settings', label: 'Project settings…' },
    { kind: 'item', id: 'switch', label: 'Switch project', submenu: true },
    { kind: 'item', id: 'new', label: 'New project…' },
    { kind: 'item', id: 'templates', label: 'Templates…' },
    { kind: 'separator' },
    { kind: 'item', id: 'open-folder', label: 'Open data folder' },
    { kind: 'separator' },
    { kind: 'item', id: 'reload', label: 'Reload (F5)' },
    { kind: 'item', id: 'release-notes', label: 'Release notes' },
  ];
}

export type SwitchProjectInput = {
  slug: string;
  name: string;
};

export type SwitchMenuEntry =
  | {
      kind: 'project';
      slug: string;
      name: string;
      current: boolean;
      disabled: boolean;
      title: string | undefined;
    }
  | { kind: 'separator' }
  | { kind: 'close'; label: 'Close project' };

/**
 * Every project, then a divider, then Close project.
 * `stateFor` is `pickerItemState` — locked projects stay disabled with its tooltip.
 */
export function switchProjectMenu(
  projects: readonly SwitchProjectInput[],
  currentSlug: string,
  stateFor: (slug: string) => PickerItemState
): SwitchMenuEntry[] {
  const rows: SwitchMenuEntry[] = projects.map((project) => {
    const state = stateFor(project.slug);
    return {
      kind: 'project',
      slug: project.slug,
      name: project.name,
      current: project.slug === currentSlug,
      disabled: state.disabled,
      title: state.title,
    };
  });
  rows.push({ kind: 'separator' });
  rows.push({ kind: 'close', label: 'Close project' });
  return rows;
}

/**
 * Open state after a click on the Switch project row.
 *
 * Hover opens the submenu on mouseenter before the click event, so a toggle
 * would shut it again. A click opens a closed submenu and keeps an open one
 * open. ArrowRight and Enter open it; Escape and ArrowLeft close it.
 */
export function submenuOpenAfterSwitchClick(openBeforeClick: boolean): boolean {
  // Not a toggle: both the closed and the hover-opened states end open.
  if (openBeforeClick) return true;
  return true;
}

export function rootFocusableIndexes(entries: readonly MenuEntry[]): number[] {
  return entries.flatMap((entry, index) => (entry.kind === 'item' ? [index] : []));
}

/** Skip dividers and projects `pickerItemState` marks disabled. */
export function switchFocusableIndexes(entries: readonly SwitchMenuEntry[]): number[] {
  return entries.flatMap((entry, index) => {
    if (entry.kind === 'separator') return [];
    if (entry.kind === 'project' && entry.disabled) return [];
    return [index];
  });
}

export type MenuNavKey = 'ArrowUp' | 'ArrowDown' | 'Home' | 'End';

/** Move within `indexes`. Up/Down wrap. Home/End jump to the ends. */
export function moveMenuFocus(
  indexes: readonly number[],
  current: number,
  key: MenuNavKey
): number {
  if (indexes.length === 0) return -1;
  if (key === 'Home') return indexes[0] ?? -1;
  if (key === 'End') return indexes[indexes.length - 1] ?? -1;
  let pos = indexes.indexOf(current);
  if (pos === -1) pos = key === 'ArrowUp' ? 0 : -1;
  const delta = key === 'ArrowDown' ? 1 : -1;
  const next = (pos + delta + indexes.length) % indexes.length;
  return indexes[next] ?? -1;
}

export const URL_PREFIX_PLACEHOLDER = 'https://jira.example.com/browse/';
export const URL_PREFIX_HINT = 'Ticket keys link to this URL plus the key.';

export type SettingsDraft = {
  name: string;
  ticketPrefix: string;
  urlPrefix: string;
};

export function settingsDraftFromProject(project: {
  name: string;
  ticket_prefix?: string | null;
  url_prefix?: string | null;
}): SettingsDraft {
  return {
    name: project.name ?? '',
    ticketPrefix: String(project.ticket_prefix ?? ''),
    urlPrefix: String(project.url_prefix ?? ''),
  };
}

export type SettingsCloseReason = 'save' | 'cancel' | 'escape' | 'templates';

/**
 * Save commits the draft. Cancel, Escape, and opening Templates leave the
 * saved project unchanged and persist nothing.
 */
export function resolveSettingsClose(
  saved: SettingsDraft,
  draft: SettingsDraft,
  reason: SettingsCloseReason
): { saved: SettingsDraft; persist: SettingsDraft | null } {
  if (reason === 'save') {
    const next = {
      name: draft.name,
      ticketPrefix: draft.ticketPrefix,
      urlPrefix: draft.urlPrefix,
    };
    return { saved: next, persist: next };
  }
  return {
    saved: { name: saved.name, ticketPrefix: saved.ticketPrefix, urlPrefix: saved.urlPrefix },
    persist: null,
  };
}

export type TemplateOption = {
  id: string;
  name: string;
  is_default: boolean;
};

export function templateOptionLabel(option: TemplateOption): string {
  return option.is_default ? `${option.name} (default)` : option.name;
}

export type NewProjectDraft = {
  name: string;
  ticketPrefix: string;
  templateId: string;
};

export function initialNewProjectDraft(defaultTemplateId?: string): NewProjectDraft {
  return {
    name: '',
    ticketPrefix: 'NEW-',
    templateId: defaultTemplateId || 'issue-tracker',
  };
}

/** Null when the name is blank — the caller shows the existing toast and does not create. */
export function newProjectCreateArgs(draft: NewProjectDraft): {
  name: string;
  ticketPrefix: string;
  templateId: string;
} | null {
  const name = draft.name.trim();
  if (!name) return null;
  return {
    name,
    ticketPrefix: draft.ticketPrefix,
    templateId: draft.templateId,
  };
}
