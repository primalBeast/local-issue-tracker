export type Project = {
  id: string;
  slug: string;
  name: string;
  waiting_state_value?: string;
  color_coding: {
    color_by_field: string;
    intensity_by_field: string;
    intensity_min: number;
    intensity_max: number;
    palette: Record<string, string>;
  };
  primary_identifier_field: string;
  ticket_prefix?: string;
  /** Absolute folder on disk for this project. */
  data_path?: string;
  compact_mode_zoom_threshold: number;
  /** Default size for newly opened item panels (user can still resize freely). */
  default_item_panel?: {
    width?: number;
    height?: number;
  };
  [key: string]: unknown;
};

export type FieldDef = {
  id: string;
  label: string;
  type: string;
  /**
   * Display order. Number or string.
   * Same row + letter suffix places fields side by side:
   * `"30a"` left, `"30b"` next, etc. Plain `30` is a full-width row.
   */
  order: number | string;
  required?: boolean;
  default?: unknown;
  options?: string[];
  validation?: Record<string, unknown>;
  placeholder?: string;
  filterable?: boolean;
  show_in_list?: boolean;
  /** Optional All Items column title (falls back to label). */
  list_label?: string;
  show_in_compact?: boolean;
  visible_when?: { field: string; equals?: unknown; not_equals?: unknown };
  help_text?: string;
  /** Share of the line, 1–100. Fields on the same line should sum to 100. */
  width?: number;
  /** When true, width is not changed when other controls on the line are resized. */
  width_lock?: boolean;
  /** Relative width within a multi-field row (default 1). Used if width is omitted. */
  width_weight?: number;
  /** Alias for width_weight. */
  flex?: number;
};

export type FieldsDoc = {
  version: number;
  fields: FieldDef[];
  system_fields?: Record<string, unknown>;
};

export type WaitingSummary = {
  is_waiting: boolean;
  current_started_at: string | null;
  current_seconds: number | null;
  total_seconds: number;
  history?: Array<Record<string, unknown>>;
};

export type Item = {
  id: string;
  sort_key: number;
  fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  version: number;
  waiting: WaitingSummary;
};

export type Panel = {
  id: string;
  kind: 'item' | 'all_items' | 'notes' | 'deliverables';
  item_id?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z_index: number;
  collapsed?: boolean;
};

export type Workspace = {
  id: string;
  name: string;
  order: number;
  /** Sidebar tab accent color (CSS color string), optional. */
  tab_color?: string | null;
  created_at: string;
  updated_at: string;
  schema_version: number;
  ui: {
    sidebar_visible: boolean;
    zoom: number;
    viewport_scroll: { x: number; y: number };
    theme?: string;
    transparent_panels?: boolean;
  };
  filters: {
    active: Record<string, unknown>;
    presets: Array<{ id: string; name: string; filter: Record<string, unknown> }>;
  };
  sort: { field: string; direction: 'asc' | 'desc' };
  panels: Panel[];
};

function formatApiError(detail: unknown): string {
  const inner =
    detail && typeof detail === 'object' && 'detail' in detail
      ? (detail as { detail: unknown }).detail
      : detail;
  if (typeof inner === 'string' && inner.trim()) return inner;
  if (Array.isArray(inner)) {
    const parts = inner.map((item) => {
      if (item && typeof item === 'object' && 'message' in item) {
        return String((item as { message: unknown }).message);
      }
      return typeof item === 'string' ? item : JSON.stringify(item);
    });
    return parts.filter(Boolean).join('\n') || 'Request failed';
  }
  if (inner && typeof inner === 'object') return JSON.stringify(inner);
  return String(detail ?? 'Request failed');
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    throw new Error(formatApiError(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string; version?: string }>('/health'),
  settings: () => req<Record<string, unknown>>('/api/settings'),
  patchSettings: (body: Record<string, unknown>) =>
    req('/api/settings', { method: 'PATCH', body: JSON.stringify(body) }),
  projects: () => req<Project[]>('/api/projects'),
  project: (slug: string) => req<Project>(`/api/projects/${slug}`),
  createProject: (body: { slug: string; name?: string; ticket_prefix?: string; template?: string }) =>
    req<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) }),
  templates: () =>
    req<{
      default: string;
      templates: Array<{
        id: string;
        name: string;
        origin: string;
        editable: boolean;
        is_default: boolean;
      }>;
    }>('/api/templates'),
  saveTemplate: (body: {
    from_project: string;
    id: string;
    name?: string;
    set_default?: boolean;
    include_layout?: boolean;
  }) =>
    req<{ id: string; name: string; origin: string; editable: boolean; is_default: boolean }>(
      '/api/templates',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  templateFields: (id: string) => req<FieldsDoc>(`/api/templates/${id}/fields`),
  putTemplateFields: (id: string, body: FieldsDoc) =>
    req<FieldsDoc>(`/api/templates/${id}/fields`, { method: 'PUT', body: JSON.stringify(body) }),
  setDefaultTemplate: (id: string) =>
    req<{
      default: string;
      templates: Array<{
        id: string;
        name: string;
        origin: string;
        editable: boolean;
        is_default: boolean;
      }>;
    }>('/api/templates/default', { method: 'POST', body: JSON.stringify({ id }) }),
  patchProject: (slug: string, body: Record<string, unknown>) =>
    req<Project>(`/api/projects/${slug}`, { method: 'PATCH', body: JSON.stringify(body) }),
  openProjectFolder: (slug: string) =>
    req<{ status: string; path: string }>(`/api/projects/${slug}/open-folder`, { method: 'POST' }),
  fields: (slug: string) => req<FieldsDoc>(`/api/projects/${slug}/fields`),
  putFields: (slug: string, body: FieldsDoc) =>
    req<FieldsDoc>(`/api/projects/${slug}/fields`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  items: (slug: string) => req<Item[]>(`/api/projects/${slug}/items`),
  item: (slug: string, id: string) => req<Item>(`/api/projects/${slug}/items/${id}`),
  createItem: (slug: string, fields: Record<string, unknown>) =>
    req<Item>(`/api/projects/${slug}/items`, {
      method: 'POST',
      body: JSON.stringify({ fields }),
    }),
  patchItem: (
    slug: string,
    id: string,
    fields: Record<string, unknown>,
    version?: number
  ) =>
    req<Item>(`/api/projects/${slug}/items/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ fields, version }),
    }),
  deleteItem: (slug: string, id: string) =>
    req(`/api/projects/${slug}/items/${id}`, { method: 'DELETE' }),
  workspaces: (slug: string) => req<Workspace[]>(`/api/projects/${slug}/workspaces`),
  workspace: (slug: string, id: string) =>
    req<Workspace>(`/api/projects/${slug}/workspaces/${id}`),
  putWorkspace: (slug: string, id: string, body: Workspace) =>
    req<Workspace>(`/api/projects/${slug}/workspaces/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  createWorkspace: (slug: string, name: string, order?: number) =>
    req<Workspace>(`/api/projects/${slug}/workspaces`, {
      method: 'POST',
      body: JSON.stringify({ name, order: order ?? 0 }),
    }),
  deleteWorkspace: (slug: string, id: string) =>
    req(`/api/projects/${slug}/workspaces/${id}`, { method: 'DELETE' }),
  notes: (slug: string) => req<{ content: unknown }>(`/api/projects/${slug}/notes`),
  putNotes: (slug: string, content: unknown) =>
    req(`/api/projects/${slug}/notes`, {
      method: 'PUT',
      body: JSON.stringify({ schema_version: 1, content }),
    }),
  deliverables: (slug: string) =>
    req<{ items: Array<Record<string, unknown>> }>(`/api/projects/${slug}/deliverables`),
  putDeliverables: (slug: string, items: Array<Record<string, unknown>>) =>
    req(`/api/projects/${slug}/deliverables`, {
      method: 'PUT',
      body: JSON.stringify({ schema_version: 1, items }),
    }),
};
