import { bodyByteLength, reserveSharedKeepalive } from './keepaliveBudget';

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
  /** Prepended to the ticket number on title-bar double-click. Empty means do not launch. */
  url_prefix?: string;
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
  visible_when?: { field: string; equals?: unknown; not_equals?: unknown; starts_with?: string };
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
  /** Last time this panel's content or layout changed. Not shown on the panel. */
  updated_at?: string;
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
  sort: {
    field: string;
    direction: 'asc' | 'desc';
    secondary?: { field: string; direction: 'asc' | 'desc' };
  };
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

/** HTTP failure from the local API. `status` 423 means another window holds the project. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function isProjectLockedError(err: unknown): boolean {
  if (err instanceof ApiError && err.status === 423) return true;
  return err instanceof Error && /open in another window/i.test(err.message);
}

/** Window id sent as X-Lit-Client. Empty until `setClientId`. */
let litClientId: string | null = null;

export function setClientId(id: string | null): void {
  litClientId = id ? id : null;
}

export function getClientId(): string | null {
  return litClientId;
}

export type ClaimResult = { ok: true } | { ok: false; heldByOther: true };

function withClient(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (litClientId) headers.set('X-Lit-Client', litClientId);
  return { ...init, headers };
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail: unknown = res.statusText;
  try {
    detail = await res.json();
  } catch {
    /* ignore */
  }
  let message = formatApiError(detail);
  if (res.status === 423 && !/open in another window/i.test(message)) {
    message = 'Project is open in another window';
  }
  return new ApiError(res.status, message);
}

/** PATCH body. A missing version tells the server to skip the version check. */
export function itemPatchBody(
  fields: Record<string, unknown>,
  version?: number | null
): string {
  if (version == null) return JSON.stringify({ fields });
  return JSON.stringify({ fields, version });
}

function keepaliveBodyBytes(body: BodyInit | null | undefined): number {
  if (typeof body === 'string') return bodyByteLength(body);
  if (body instanceof Uint8Array) return body.byteLength;
  return 0;
}

function withoutKeepalive(init: RequestInit): RequestInit {
  if (init.keepalive !== true) return init;
  const next: RequestInit = { ...init };
  delete next.keepalive;
  return next;
}

function isFetchTypeError(err: unknown): boolean {
  return err instanceof TypeError || (err instanceof Error && err.name === 'TypeError');
}

/**
 * `keepalive: true` shares a 64 KiB browser budget. Bodies that do not fit
 * go out as a normal fetch. A keepalive fetch that throws, or rejects with
 * TypeError, is retried once without keepalive.
 */
async function fetchWithKeepalive(path: string, init: RequestInit): Promise<Response> {
  if (init.keepalive !== true) return fetch(path, init);
  const release = reserveSharedKeepalive(keepaliveBodyBytes(init.body));
  if (!release) return fetch(path, withoutKeepalive(init));
  const retry = () => fetch(path, withoutKeepalive(init));
  try {
    let pending: Promise<Response>;
    try {
      pending = fetch(path, init);
    } catch {
      release();
      return retry();
    }
    try {
      const res = await pending;
      release();
      return res;
    } catch (err) {
      release();
      if (isFetchTypeError(err)) return retry();
      throw err;
    }
  } catch (err) {
    release();
    throw err;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetchWithKeepalive(path, withClient(init));
  if (!res.ok) throw await errorFrom(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  setClientId,
  getClientId,
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
  openSplit: (left: string, right: string) =>
    req<{ status: string; positioned?: boolean }>('/api/desktop/open-split', {
      method: 'POST',
      body: JSON.stringify({ left, right }),
    }),
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
    version?: number | null,
    opts?: { keepalive?: boolean }
  ) =>
    req<Item>(`/api/projects/${slug}/items/${id}`, {
      method: 'PATCH',
      body: itemPatchBody(fields, version),
      ...(opts?.keepalive ? { keepalive: true } : {}),
    }),
  deleteItem: (slug: string, id: string) =>
    req(`/api/projects/${slug}/items/${id}`, { method: 'DELETE' }),
  workspaces: (slug: string) => req<Workspace[]>(`/api/projects/${slug}/workspaces`),
  workspace: (slug: string, id: string) =>
    req<Workspace>(`/api/projects/${slug}/workspaces/${id}`),
  putWorkspace: (slug: string, id: string, body: Workspace, opts?: { keepalive?: boolean }) =>
    req<Workspace>(`/api/projects/${slug}/workspaces/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
      ...(opts?.keepalive ? { keepalive: true } : {}),
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
  /** 200 if free or already ours. 409 is heldByOther and does not throw. */
  claimProject: async (slug: string): Promise<ClaimResult> => {
    const res = await fetch(`/api/projects/${slug}/claim`, withClient({ method: 'POST' }));
    if (res.status === 409) {
      try {
        await res.json();
      } catch {
        /* ignore */
      }
      return { ok: false, heldByOther: true };
    }
    if (!res.ok) throw await errorFrom(res);
    try {
      await res.json();
    } catch {
      /* empty body */
    }
    return { ok: true };
  },
  releaseProject: (slug: string, opts?: { keepalive?: boolean }) =>
    req<{ released: boolean }>(`/api/projects/${slug}/release`, {
      method: 'POST',
      ...(opts?.keepalive ? { keepalive: true } : {}),
    }),
  /** Releases every project this client holds. Used on window close. */
  releaseAll: (opts?: { keepalive?: boolean; signal?: AbortSignal }) =>
    req<{ released: string[] }>(
      `/api/session/release-all?client=${encodeURIComponent(litClientId ?? '')}`,
      {
        method: 'POST',
        ...(opts?.keepalive ? { keepalive: true } : {}),
        ...(opts?.signal ? { signal: opts.signal } : {}),
      }
    ),
  claims: () => req<{ claims: Record<string, string> }>('/api/session/claims'),
};
