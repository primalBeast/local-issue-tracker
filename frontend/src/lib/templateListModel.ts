import { BUILTIN_LABEL, DEFAULT_BADGE, PROJECT_FIELDS_LABEL } from './templateLabels';

export type TemplateInfo = {
  id: string;
  name: string;
  origin: string;
  editable: boolean;
  is_default: boolean;
};

export type TemplateSource = 'project' | string;

export type NamedTemplateEntry = {
  kind: 'builtin' | 'saved';
  id: string;
  label: string;
  selected: boolean;
  badge: string | null;
  readOnly: boolean;
};

export type TemplateListEntry =
  | { kind: 'project'; id: 'project'; label: string; selected: boolean }
  | NamedTemplateEntry;

export function builtinTemplate(templates: TemplateInfo[]): TemplateInfo | undefined {
  return templates.find((t) => t.origin === 'shipped') ?? templates.find((t) => t.is_default);
}

export function savedTemplates(templates: TemplateInfo[]): TemplateInfo[] {
  const app = builtinTemplate(templates);
  return templates.filter((t) => t.id !== app?.id);
}

export function dialogTitle(source: TemplateSource, templates: TemplateInfo[], projectName: string): string {
  if (source === 'project') return PROJECT_FIELDS_LABEL;
  return templates.find((t) => t.id === source)?.name || projectName || 'Templates';
}

export function listEntries(templates: TemplateInfo[], source: TemplateSource): {
  project: Extract<TemplateListEntry, { kind: 'project' }>;
  builtin: NamedTemplateEntry | null;
  saved: NamedTemplateEntry[];
} {
  const app = builtinTemplate(templates);
  const builtin: NamedTemplateEntry | null = app
    ? {
        kind: 'builtin',
        id: app.id,
        label: BUILTIN_LABEL,
        selected: source === app.id,
        badge: app.is_default ? DEFAULT_BADGE : null,
        readOnly: true,
      }
    : null;
  const saved: NamedTemplateEntry[] = savedTemplates(templates).map((t) => ({
    kind: 'saved',
    id: t.id,
    label: t.name,
    selected: source === t.id,
    badge: t.is_default ? DEFAULT_BADGE : null,
    readOnly: !t.editable,
  }));
  return {
    project: {
      kind: 'project',
      id: 'project',
      label: PROJECT_FIELDS_LABEL,
      selected: source === 'project',
    },
    builtin,
    saved,
  };
}
