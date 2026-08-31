<script lang="ts">
  import { onMount } from 'svelte';
  import {
    api,
    type FieldDef,
    type Item,
    type Panel,
    type Project,
    type Workspace,
  } from './lib/api';
  import { panelColors } from './lib/color';
  import { isVisible, itemMatchesFilters, sortItems } from './lib/filters';
  import FieldRenderer from './lib/FieldRenderer.svelte';
  import FloatingPanel from './lib/FloatingPanel.svelte';
  import ItemTitleBar from './lib/ItemTitleBar.svelte';
  import TemplateEditor from './lib/TemplateEditor.svelte';
  import RichText from './lib/RichText.svelte';
  import { fieldFlex, groupBodyBlocks, groupFieldsByRow, pickField } from './lib/fieldLayout';
  import { HEADER_TITLE_EDITOR_PX, isNotesFillRow, minItemPanelHeight } from './lib/panelSize';
  import {
    isPanelSortField,
    layoutColumnMajor,
    PANEL_SORT_OPTIONS,
    sortItemPanels,
    type PanelSortField,
  } from './lib/panelSort';
  import { clampZoom, snapToGrid } from './lib/snap';
  import {
    defaultPan,
    fitView,
    focusView,
    panAfterZoom,
    panelsWorldBounds,
    screenToWorld,
    zoomFromPointerScrub,
    zoomFromWheelDelta,
  } from './lib/viewport';
  import {
    formatWaitingDays,
    isItemWaiting,
    liveSeconds,
    todayLocalDate,
    waitingNameChoices,
  } from './lib/waiting';
  import { nextTicketKey, normalizeTicketPrefix, slugFromName, uniqueSlug } from './lib/ticketPrefix';
  import { ticketHref } from './lib/ticketUrl';
  import { isExternalTicketId, slotsToShow } from './lib/urlTicket';
  import {
    appearanceFromWorkspace,
    applyPanelTransparency,
    applyTheme,
    applyTransparentPanels,
    parseTransparencyMap,
    parseTransparentPanels,
    resolveTheme,
    THEME_STORAGE_KEY,
    THEMES,
    TRANSPARENCY_BY_THEME_KEY,
    TRANSPARENT_PANELS_KEY,
    transparencyForTheme,
  } from './lib/themes';

  let projects = $state<Project[]>([]);
  let project = $state<Project | null>(null);
  let fieldsDoc = $state<{ fields: FieldDef[] } | null>(null);
  let items = $state<Item[]>([]);
  let workspaces = $state<Workspace[]>([]);
  let workspace = $state<Workspace | null>(null);
  let notesContent = $state<unknown>({ type: 'doc', content: [] });
  let deliverables = $state<Array<Record<string, unknown>>>([]);
  let detailCache = $state<Record<string, Item>>({});
  let loading = $state(true);
  let error = $state<string | null>(null);
  let toast = $state<string | null>(null);
  let nowTick = $state(Date.now());
  let saveTimer: ReturnType<typeof setTimeout> | null = null;
  let itemSaveTimers: Record<string, ReturnType<typeof setTimeout>> = {};
  /** Pointer-based tab reorder. Click still selects unless a drag happened. */
  let dragWsId = $state<string | null>(null);
  const tabDrag = {
    id: null as string | null,
    startX: 0,
    startY: 0,
    dragging: false,
    dirty: false,
    /** When true, the next click is from a completed drag — ignore it. */
    suppressClick: false,
    pointerId: -1,
    origList: null as Workspace[] | null,
  };
  /** Board rename / tab color editor (right-click a tab). */
  let boardEditor = $state<{
    id: string;
    name: string;
    tab_color: string | null;
    x: number;
    y: number;
  } | null>(null);
  let boardRemoveConfirm = $state<{ id: string; name: string } | null>(null);
  let itemDeleteConfirm = $state<{ id: string; name: string } | null>(null);
  let templateEditorOpen = $state(false);
  /** Extra External Fixing ticket-URL slots revealed with +. */
  let extraTicketSlots = $state<Record<string, number>>({});
  let itemContextMenu = $state<{
    itemId?: string;
    panelId?: string;
    name: string;
    x: number;
    y: number;
  } | null>(null);
  let projectEditor = $state<{
    name: string;
    ticket_prefix: string;
    url_prefix: string;
    newName: string;
    newPrefix: string;
    newTemplate: string;
    templates: Array<{ id: string; name: string; is_default: boolean }>;
  } | null>(null);

  const TAB_COLOR_SWATCHES: (string | null)[] = [
    null,
    '#3b82f6',
    '#8b5cf6',
    '#06b6d4',
    '#22c55e',
    '#84cc16',
    '#f59e0b',
    '#f97316',
    '#ef4444',
    '#ec4899',
    '#a78bfa',
    '#64748b',
  ];

  let fieldDefs = $derived(fieldsDoc?.fields || []);
  let bodyFieldRows = $derived(
    groupFieldsByRow(fieldDefs.filter((f) => !isHeaderManagedField(f)))
  );
  let bodyFieldBlocks = $derived(groupBodyBlocks(bodyFieldRows));
  let listFields = $derived(
    [...fieldDefs]
      .filter((f) => f.show_in_list)
      .sort((a, b) => String(a.order).localeCompare(String(b.order), undefined, { numeric: true }))
  );
  const ALL_ITEMS_FILTER_ROW_IDS: string[] = ['state', 'dn_assigned_to', 'customer_assigned_to'];
  const ALL_ITEMS_HIDDEN_FILTER_IDS: string[] = ['priority', 'urgency', 'waiting_for'];
  const ASSIGNED_FILTER_IDS: string[] = ['dn_assigned_to', 'customer_assigned_to'];

  function filterCheckboxOptions(ff: FieldDef): string[] {
    const opts = ff.options || [];
    if (!ASSIGNED_FILTER_IDS.includes(ff.id)) return opts;
    return opts.filter((o) => {
      const s = String(o ?? '').trim();
      return s !== '' && s !== '-';
    });
  }
  let filterableFields = $derived(
    fieldDefs.filter((f) => f.filterable && !ALL_ITEMS_HIDDEN_FILTER_IDS.includes(f.id))
  );
  let filterRowFields = $derived(
    ALL_ITEMS_FILTER_ROW_IDS
      .map((id) => filterableFields.find((f) => f.id === id))
      .filter((f): f is FieldDef => f != null)
  );
  let otherFilterFields = $derived(
    filterableFields.filter((f) => !ALL_ITEMS_FILTER_ROW_IDS.includes(f.id))
  );
  let zoom = $derived(workspace?.ui.zoom ?? 1);
  let pan = $derived(workspace?.ui.viewport_scroll ?? defaultPan());
  let compact = $derived(
    !!project && zoom < (project.compact_mode_zoom_threshold ?? 0.33)
  );
  let sidebarVisible = $derived(workspace?.ui.sidebar_visible ?? true);
  let panning = $state(false);
  let sortBy = $state<PanelSortField>('ticket_key');
  const initialTheme = resolveTheme(readStoredTheme());
  const initialTransparent = readStoredTransparentPanels();
  const initialTransparencyMap = readStoredTransparencyMap();
  let themeId = $state(initialTheme.id);
  let committedThemeId = $state(initialTheme.id);
  let highlightedThemeId = $state(initialTheme.id);
  let themeMenuOpen = $state(false);
  let transparentPanels = $state(initialTransparent);
  let transparencyByTheme = $state<Record<string, number>>(initialTransparencyMap);
  const initialPanelTransparency = transparencyForTheme(initialTheme.id, initialTransparencyMap);
  let panelTransparency = $state(initialPanelTransparency);
  let transparencySaveTimer: ReturnType<typeof setTimeout> | null = null;
  applyTheme(initialTheme.id);
  applyTransparentPanels(initialTransparent);
  applyPanelTransparency(initialPanelTransparency);
  let canvasWrapEl = $state<HTMLElement | null>(null);
  let appShellEl = $state<HTMLElement | null>(null);
  let serverOk = $state(true);
  const canvasPan = {
    pointerId: -1,
    startX: 0,
    startY: 0,
    origX: 0,
    origY: 0,
    swallowClicks: false,
  };

  /** Main Board (seed id) is always pinned to the top of the tab list. */
  function isMainBoard(w: Workspace): boolean {
    return w.id === 'ws-main';
  }

  function sortWorkspaces(list: Workspace[]): Workspace[] {
    return [...list].sort(
      (a, b) =>
        (a.order ?? 0) - (b.order ?? 0) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id)
    );
  }

  let filteredItems = $derived(
    workspace
      ? sortItems(
          items.filter((it) => itemMatchesFilters(it, workspace!.filters.active, fieldDefs)),
          workspace.sort,
          fieldDefs
        )
      : items
  );
  let listHasWaiting = $derived(filteredItems.some(isItemWaiting));
  let allItemsColumns = $derived(
    listHasWaiting ? listFields : listFields.filter((f) => f.id !== 'waiting_for')
  );
  let openItemIds = $derived(
    new Set(
      (workspace?.panels || [])
        .filter((p) => p.kind === 'item' && p.item_id)
        .map((p) => p.item_id as string)
    )
  );

  onMount(() => {
    const tick = setInterval(() => (nowTick = Date.now()), 1000);
    const healthTick = setInterval(() => void pingServer(), 4000);
    void pingServer();
    void bootstrap();
    const onKey = (e: KeyboardEvent) => {
      if (themeMenuOpen) {
        const t = e.target as HTMLElement | null;
        const isRange = t instanceof HTMLInputElement && t.type === 'range';
        const themeKey =
          e.key === 'Escape' ||
          e.key === 'Enter' ||
          e.key === 'Home' ||
          e.key === 'End' ||
          ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !isRange);
        if (themeKey) {
          onThemePickerKey(e);
          e.stopPropagation();
          return;
        }
      }
      if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        toggleSidebar();
      }
      if (e.key === 'Escape') {
        if (tabDrag.dragging || tabDrag.id) {
          e.preventDefault();
          cancelTabDrag();
          return;
        }
        if (itemDeleteConfirm) {
          itemDeleteConfirm = null;
          return;
        }
        if (itemContextMenu) {
          itemContextMenu = null;
          return;
        }
        if (boardRemoveConfirm) {
          boardRemoveConfirm = null;
          return;
        }
        if (templateEditorOpen) {
          templateEditorOpen = false;
          return;
        }
        if (projectEditor) {
          void closeProjectEditor(true);
          return;
        }
        boardEditor = null;
      }
      if ((e.metaKey || e.ctrlKey) && (e.key === '=' || e.key === '+' || e.key === 'Add')) {
        e.preventDefault();
        zoomByKeyboard(1.12);
      }
      if ((e.metaKey || e.ctrlKey) && (e.key === '-' || e.key === '_' || e.key === 'Subtract')) {
        e.preventDefault();
        zoomByKeyboard(1 / 1.12);
      }
      if ((e.metaKey || e.ctrlKey) && (e.key === '0' || e.key === 'Numpad0')) {
        e.preventDefault();
        zoomByKeyboard(0);
      }
    };
    // Only close board editor when clicking outside it — do not interfere
    // with panel drag, resize, or tab clicks.
    const onDocPointerDown = (e: PointerEvent) => {
      const t = e.target as HTMLElement | null;
      if (itemDeleteConfirm) {
        if (!t?.closest?.('.confirm-dialog')) itemDeleteConfirm = null;
        return;
      }
      if (itemContextMenu) {
        if (!t?.closest?.('.item-context-menu')) itemContextMenu = null;
        return;
      }
      if (boardRemoveConfirm) {
        if (!t?.closest?.('.confirm-dialog')) boardRemoveConfirm = null;
        return;
      }
      if (templateEditorOpen) {
        if (!t?.closest?.('.template-editor')) templateEditorOpen = false;
        return;
      }
      if (projectEditor && !t?.closest?.('.project-editor') && !t?.closest?.('.brand')) {
        void closeProjectEditor(true);
      }
      if (!boardEditor) return;
      if (t?.closest?.('.board-editor')) return;
      if (t?.closest?.('.ws-tab')) return; // tab open/context menu owns the click
      boardEditor = null;
    };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDocPointerDown, true);
    return () => {
      clearInterval(tick);
      clearInterval(healthTick);
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener('pointerdown', onDocPointerDown, true);
      endCanvasPan();
      clearCtrlPanClickSuppress();
      endZoomScrub();
      resetTabDrag();
    };
  });

  async function pingServer() {
    try {
      const h = await api.health();
      serverOk = h.status === 'ok';
    } catch {
      serverOk = false;
    }
  }

  async function bootstrap() {
    try {
      loading = true;
      projects = await api.projects();
      if (!projects.length) {
        error = 'No projects found. Run lit serve to auto-seed, or lit init-project.';
        return;
      }
      const settings = await api.settings();
      adoptTheme((settings.theme as string) || readStoredTheme());
      adoptTransparentPanels(
        settings.transparent_panels !== undefined
          ? settings.transparent_panels
          : readStoredTransparentPanels()
      );
      const serverMap = parseTransparencyMap(settings.transparency_by_theme);
      const mergedMap = { ...readStoredTransparencyMap(), ...serverMap };
      transparencyByTheme = mergedMap;
      writeStoredTransparencyMap(mergedMap);
      adoptTransparencyForTheme(themeId, mergedMap);
      const slug =
        (settings.last_project_slug as string) || projects[0].slug;
      await loadProject(slug);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  function readStoredTheme(): string | null {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function writeStoredTheme(id: string) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id);
    } catch {
      /* ignore quota / private mode */
    }
  }

  function readStoredTransparentPanels(): boolean {
    try {
      return parseTransparentPanels(localStorage.getItem(TRANSPARENT_PANELS_KEY));
    } catch {
      return false;
    }
  }

  function writeStoredTransparentPanels(on: boolean) {
    try {
      localStorage.setItem(TRANSPARENT_PANELS_KEY, on ? '1' : '0');
    } catch {
      /* ignore quota / private mode */
    }
  }

  function readStoredTransparencyMap(): Record<string, number> {
    try {
      return parseTransparencyMap(JSON.parse(localStorage.getItem(TRANSPARENCY_BY_THEME_KEY) || '{}'));
    } catch {
      return {};
    }
  }

  function writeStoredTransparencyMap(map: Record<string, number>) {
    try {
      localStorage.setItem(TRANSPARENCY_BY_THEME_KEY, JSON.stringify(map));
    } catch {
      /* ignore quota / private mode */
    }
  }

  function adoptTransparencyForTheme(id: string, map?: Record<string, number>) {
    const n = applyPanelTransparency(transparencyForTheme(id, map ?? transparencyByTheme));
    panelTransparency = n;
    return n;
  }

  function setPanelTransparency(amount: number) {
    const n = applyPanelTransparency(amount);
    panelTransparency = n;
    const next = { ...transparencyByTheme, [themeId]: n };
    transparencyByTheme = next;
    writeStoredTransparencyMap(next);
    if (transparencySaveTimer) clearTimeout(transparencySaveTimer);
    transparencySaveTimer = setTimeout(() => {
      void api.patchSettings({ transparency_by_theme: next }).catch((e) => {
        console.error('Failed to persist theme transparency', e);
      });
    }, 280);
  }

  function adoptTransparentPanels(raw: unknown) {
    const on = applyTransparentPanels(parseTransparentPanels(raw));
    transparentPanels = on;
    writeStoredTransparentPanels(on);
    return on;
  }

  async function setTransparentPanels(on: boolean) {
    adoptTransparentPanels(on);
    updateWorkspace((ws) => {
      ws.ui.transparent_panels = on;
    });
    try {
      await api.patchSettings({ transparent_panels: on });
    } catch (e) {
      console.error('Failed to persist transparent panels', e);
    }
  }

  function adoptTheme(id: string | null | undefined) {
    const theme = applyTheme(id);
    themeId = theme.id;
    highlightedThemeId = theme.id;
    writeStoredTheme(theme.id);
    adoptTransparencyForTheme(theme.id);
    return theme;
  }

  function previewTheme(id: string) {
    const theme = applyTheme(id);
    themeId = theme.id;
    highlightedThemeId = theme.id;
    adoptTransparencyForTheme(theme.id);
    return theme;
  }

  function openThemeMenu() {
    themeMenuOpen = true;
    highlightedThemeId = committedThemeId;
    queueMicrotask(() => {
      const el = document.querySelector('.theme-dialog') as HTMLElement | null;
      el?.focus();
      scrollThemeHighlightIntoView(highlightedThemeId);
    });
  }

  function closeThemeMenu(revert: boolean) {
    if (revert) previewTheme(committedThemeId);
    themeMenuOpen = false;
  }

  function scrollThemeHighlightIntoView(id: string) {
    queueMicrotask(() => {
      const item = document.querySelector(
        `.theme-menu [data-theme-id="${CSS.escape(id)}"]`
      ) as HTMLElement | null;
      item?.scrollIntoView({ block: 'nearest' });
    });
  }

  function moveThemeHighlight(delta: number) {
    if (!themeMenuOpen) openThemeMenu();
    const idx = THEMES.findIndex((t) => t.id === highlightedThemeId);
    const next = THEMES[(Math.max(idx, 0) + delta + THEMES.length) % THEMES.length];
    previewTheme(next.id);
    scrollThemeHighlightIntoView(next.id);
  }

  function onThemePickerKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      moveThemeHighlight(1);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      moveThemeHighlight(-1);
      return;
    }
    if (e.key === 'Home') {
      e.preventDefault();
      if (!themeMenuOpen) openThemeMenu();
      previewTheme(THEMES[0].id);
      scrollThemeHighlightIntoView(THEMES[0].id);
      return;
    }
    if (e.key === 'End') {
      e.preventDefault();
      if (!themeMenuOpen) openThemeMenu();
      const last = THEMES[THEMES.length - 1];
      previewTheme(last.id);
      scrollThemeHighlightIntoView(last.id);
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (themeMenuOpen) void setTheme(highlightedThemeId);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      closeThemeMenu(true);
    }
  }

  async function setTheme(id: string) {
    const theme = adoptTheme(id);
    committedThemeId = theme.id;
    themeMenuOpen = false;
    updateWorkspace((ws) => {
      ws.ui.theme = theme.id;
    });
    try {
      await api.patchSettings({ theme: theme.id });
    } catch (e) {
      console.error('Failed to persist theme', e);
    }
  }

  function applyBoardAppearance(ws: Workspace) {
    const look = appearanceFromWorkspace(
      ws.ui,
      readStoredTheme(),
      readStoredTransparentPanels()
    );
    adoptTheme(look.theme);
    committedThemeId = look.theme;
    themeMenuOpen = false;
    adoptTransparentPanels(look.transparent);
    if (ws.ui.theme == null || ws.ui.transparent_panels == null) {
      updateWorkspace((w) => {
        if (w.ui.theme == null) w.ui.theme = look.theme;
        if (w.ui.transparent_panels == null) w.ui.transparent_panels = look.transparent;
      });
    }
  }

  function prefixStorageKey(slug: string) {
    return `lit:ticketPrefix:${slug}`;
  }

  function readStoredPrefix(slug: string): string | null {
    try {
      return localStorage.getItem(prefixStorageKey(slug));
    } catch {
      return null;
    }
  }

  function writeStoredPrefix(slug: string, prefix: string) {
    try {
      localStorage.setItem(prefixStorageKey(slug), prefix);
    } catch {
      /* ignore */
    }
  }

  function localLastWsKey(slug: string) {
    return `lit:lastWorkspace:${slug}`;
  }

  function readLocalLastWorkspace(slug: string): string | null {
    try {
      return localStorage.getItem(localLastWsKey(slug));
    } catch {
      return null;
    }
  }

  function writeLocalLastWorkspace(slug: string, wsId: string) {
    try {
      localStorage.setItem(localLastWsKey(slug), wsId);
    } catch {
      /* ignore quota / private mode */
    }
  }

  async function rememberLastWorkspace(wsId: string) {
    if (!project) return;
    // Always persist client-side so a plain browser reload restores the board
    // even if the settings API fails or an old server is still running.
    writeLocalLastWorkspace(project.slug, wsId);
    try {
      await api.patchSettings({
        last_project_slug: project.slug,
        last_workspace_by_project: { [project.slug]: wsId },
      });
    } catch (e) {
      console.error('Failed to persist last workspace to server settings', e);
    }
  }

  async function loadProject(slug: string) {
    project = await api.project(slug);
    const serverPrefix = project.ticket_prefix;
    const localPrefix = readStoredPrefix(slug);
    if (serverPrefix && serverPrefix !== 'NEW-') {
      writeStoredPrefix(slug, serverPrefix);
    } else if (localPrefix && localPrefix !== (serverPrefix || 'NEW-')) {
      project = { ...project, ticket_prefix: localPrefix };
      try {
        const saved = await api.patchProject(slug, { ticket_prefix: localPrefix });
        project = { ...saved, ticket_prefix: saved.ticket_prefix || localPrefix };
      } catch (e) {
        console.error(e);
      }
    } else if (serverPrefix) {
      writeStoredPrefix(slug, serverPrefix);
    }
    fieldsDoc = await api.fields(slug);
    items = await api.items(slug);
    workspaces = sortWorkspaces(await api.workspaces(slug));
    notesContent = (await api.notes(slug)).content;
    deliverables = (await api.deliverables(slug)).items || [];
    detailCache = {};

    // Prefer server settings, fall back to localStorage
    let lastWsId: string | null = null;
    try {
      const settings = await api.settings();
      const lastMap = (settings.last_workspace_by_project || {}) as Record<string, string>;
      lastWsId = lastMap[slug] || null;
    } catch (e) {
      console.error(e);
    }
    if (!lastWsId) {
      lastWsId = readLocalLastWorkspace(slug);
    }

    const preferred =
      (lastWsId && workspaces.find((w) => w.id === lastWsId)) || workspaces[0] || null;
    workspace = preferred ? cloneWorkspace(preferred) : null;
    if (workspace?.sort?.field && isPanelSortField(workspace.sort.field)) {
      sortBy = workspace.sort.field;
    }

    // Do not overwrite last_workspace when only updating last_project_slug
    try {
      await api.patchSettings({ last_project_slug: slug });
    } catch (e) {
      console.error(e);
    }

    if (workspace) {
      applyBoardAppearance(workspace);
      // Sync both stores to whatever we actually opened
      writeLocalLastWorkspace(slug, workspace.id);
      for (const p of workspace.panels) {
        if (p.kind === 'item' && p.item_id) await ensureDetail(p.item_id);
      }
    }
  }

  async function ensureDetail(id: string) {
    if (detailCache[id]) return detailCache[id];
    if (!project) return null;
    const full = await api.item(project.slug, id);
    detailCache = { ...detailCache, [id]: full };
    return full;
  }

  /** Deep clone without relying on structuredClone(proxy) (Svelte $state). */
  function cloneWorkspace(ws: Workspace): Workspace {
    return JSON.parse(JSON.stringify(ws)) as Workspace;
  }

  /** Keep the workspaces list in sync with the in-memory current workspace. */
  function flushCurrentWorkspaceToList() {
    if (!workspace) return;
    const snap = cloneWorkspace(workspace);
    const idx = workspaces.findIndex((w) => w.id === snap.id);
    if (idx >= 0) {
      workspaces = workspaces.map((w) => (w.id === snap.id ? snap : w));
    } else {
      workspaces = [...workspaces, snap];
    }
  }

  function scheduleWorkspaceSave() {
    if (!project || !workspace) return;
    // Always mirror latest local state into the list immediately
    const id = workspace.id;
    flushCurrentWorkspaceToList();

    if (saveTimer) clearTimeout(saveTimer);
    const slug = project.slug;
    saveTimer = setTimeout(async () => {
      const toSave = workspaces.find((w) => w.id === id);
      if (!toSave) return;
      try {
        const saved = await api.putWorkspace(slug, id, toSave);
        workspaces = workspaces.map((w) => (w.id === id ? saved : w));
        // Do not replace the live workspace if the user has already switched away
        if (workspace?.id === id) {
          workspace = {
            ...cloneWorkspace(workspace),
            updated_at: saved.updated_at,
          };
        }
      } catch (e) {
        showToast('Failed to save layout');
        console.error(e);
      }
    }, 400);
  }

  function updateWorkspace(mutator: (ws: Workspace) => void) {
    if (!workspace) return;
    const next = cloneWorkspace(workspace);
    mutator(next);
    workspace = next;
    scheduleWorkspaceSave();
  }

  function toggleSidebar() {
    updateWorkspace((ws) => {
      ws.ui.sidebar_visible = !ws.ui.sidebar_visible;
    });
  }

  async function selectWorkspace(id: string) {
    if (!project) return;
    if (workspace?.id === id) return;

    // Persist current workspace into the list before leaving it
    flushCurrentWorkspaceToList();

    // Switch immediately from local list so the tab always responds
    const local = workspaces.find((x) => x.id === id);
    if (!local) {
      showToast('Board not found');
      return;
    }
    workspace = cloneWorkspace(local);
    if (workspace.sort?.field && isPanelSortField(workspace.sort.field)) {
      sortBy = workspace.sort.field;
    }
    applyBoardAppearance(workspace);
    void rememberLastWorkspace(id);

    // Refresh from server in the background (do not block UI)
    try {
      const fresh = await api.workspace(project.slug, id);
      if (workspace?.id !== id) return; // user already switched again
      workspace = fresh;
      workspaces = sortWorkspaces(workspaces.map((w) => (w.id === id ? fresh : w)));
      applyBoardAppearance(workspace);
      for (const p of fresh.panels || []) {
        if (p.kind === 'item' && p.item_id) await ensureDetail(p.item_id);
      }
    } catch (e) {
      // Keep local board; do not stick the user on a failed network call
      console.error(e);
    }
  }

  async function persistWorkspaceOrders(list: Workspace[], fallback?: Workspace[] | null) {
    if (!project) return;
    try {
      const savedList = await Promise.all(
        list.map((w) => api.putWorkspace(project!.slug, w.id, w))
      );
      workspaces = sortWorkspaces(savedList);
      if (workspace) {
        const cur = savedList.find((w) => w.id === workspace!.id);
        if (cur) {
          workspace = {
            ...cloneWorkspace(workspace),
            order: cur.order,
            updated_at: cur.updated_at,
          };
        }
      }
    } catch (e) {
      if (fallback) workspaces = sortWorkspaces(fallback.map(cloneWorkspace));
      showToast('Failed to save board order');
      console.error(e);
    }
  }

  function withTabOrders(list: Workspace[]): Workspace[] {
    return list.map((w, i) => {
      const next = cloneWorkspace(w);
      next.order = i + 1;
      return next;
    });
  }

  function tabInsertBeforeAtClientY(clientY: number): number {
    const tabs = Array.from(
      document.querySelectorAll<HTMLElement>('.sidebar .ws-tab[data-ws-id]')
    );
    for (let i = 0; i < tabs.length; i++) {
      const r = tabs[i].getBoundingClientRect();
      if (clientY < r.top + r.height / 2) return i;
    }
    return tabs.length;
  }

  function moveWorkspaceToInsertBefore(fromId: string, insertBefore: number) {
    const fromIdx = workspaces.findIndex((w) => w.id === fromId);
    if (fromIdx < 0) return;
    let dest = insertBefore;
    if (fromIdx < dest) dest -= 1;
    dest = Math.max(0, Math.min(dest, workspaces.length - 1));
    if (dest === fromIdx) return;
    const next = workspaces.map(cloneWorkspace);
    const [moved] = next.splice(fromIdx, 1);
    next.splice(dest, 0, moved);
    workspaces = withTabOrders(next);
    tabDrag.dirty = true;
  }

  function clearTabWindowListeners() {
    window.removeEventListener('pointermove', onTabWindowMove, true);
    window.removeEventListener('pointerup', onTabWindowUp, true);
    window.removeEventListener('pointercancel', onTabWindowUp, true);
  }

  function resetTabDrag() {
    tabDrag.id = null;
    tabDrag.dragging = false;
    tabDrag.dirty = false;
    tabDrag.pointerId = -1;
    tabDrag.origList = null;
    dragWsId = null;
    document.body.classList.remove('lit-tab-dragging');
    clearTabWindowListeners();
  }

  function cancelTabDrag() {
    if (tabDrag.origList) {
      workspaces = sortWorkspaces(tabDrag.origList.map(cloneWorkspace));
    }
    resetTabDrag();
    if (workspace) scheduleWorkspaceSave();
  }

  /** Board select — click opens; a completed drag does not. */
  function onTabClick(id: string) {
    if (tabDrag.suppressClick) {
      tabDrag.suppressClick = false;
      return;
    }
    void selectWorkspace(id);
  }

  function onTabPointerDown(e: PointerEvent, id: string) {
    if (e.button !== 0) return;
    flushCurrentWorkspaceToList();
    tabDrag.id = id;
    tabDrag.startX = e.clientX;
    tabDrag.startY = e.clientY;
    tabDrag.dragging = false;
    tabDrag.dirty = false;
    tabDrag.suppressClick = false;
    tabDrag.pointerId = e.pointerId;
    tabDrag.origList = workspaces.map(cloneWorkspace);
    clearTabWindowListeners();
    window.addEventListener('pointermove', onTabWindowMove, true);
    window.addEventListener('pointerup', onTabWindowUp, true);
    window.addEventListener('pointercancel', onTabWindowUp, true);
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }

  function onTabWindowMove(e: PointerEvent) {
    if (tabDrag.pointerId !== e.pointerId || !tabDrag.id) return;
    if (workspaces.length < 2) return;

    const dx = Math.abs(e.clientX - tabDrag.startX);
    const dy = Math.abs(e.clientY - tabDrag.startY);
    if (!tabDrag.dragging && (dx > 6 || dy > 6)) {
      tabDrag.dragging = true;
      dragWsId = tabDrag.id;
      tabDrag.suppressClick = true;
      document.body.classList.add('lit-tab-dragging');
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
    }
    if (!tabDrag.dragging) return;
    e.preventDefault();
    moveWorkspaceToInsertBefore(tabDrag.id, tabInsertBeforeAtClientY(e.clientY));
  }

  function onTabWindowUp(e: PointerEvent) {
    if (tabDrag.pointerId !== e.pointerId) return;
    const wasDrag = tabDrag.dragging;
    const dirty = tabDrag.dirty;
    const snapshot = tabDrag.origList;
    const list = workspaces;
    resetTabDrag();
    if (wasDrag) {
      e.preventDefault();
      if (dirty) void persistWorkspaceOrders(list, snapshot);
    }
  }

  function wheelShouldZoom(e: WheelEvent): boolean {
    // Pinch-zoom and Ctrl/Cmd+wheel always zoom the canvas.
    if (e.ctrlKey || e.metaKey) return true;
    const t = e.target as HTMLElement | null;
    // Let scrollable panel contents keep native scroll unless a modifier is held.
    if (t?.closest?.('.panel-body')) return false;
    return true;
  }

  function applyZoomAtClient(clientX: number, clientY: number, newZoom: number) {
    if (!workspace) return;
    const wrap = canvasWrapEl;
    if (!wrap) return;
    const oldZ = workspace.ui.zoom || 1;
    const z = clampZoom(newZoom);
    if (Math.abs(z - oldZ) < 1e-4) return;
    const rect = wrap.getBoundingClientRect();
    const pointer = { x: clientX - rect.left, y: clientY - rect.top };
    const curPan = workspace.ui.viewport_scroll ?? defaultPan();
    updateWorkspace((ws) => {
      ws.ui.zoom = z;
      ws.ui.viewport_scroll = panAfterZoom(curPan, oldZ, z, pointer);
    });
  }

  function zoomByKeyboard(factor: number) {
    const wrap = canvasWrapEl;
    if (!wrap || !workspace) return;
    const rect = wrap.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (factor === 0) {
      applyZoomAtClient(cx, cy, 1);
      return;
    }
    applyZoomAtClient(cx, cy, (workspace.ui.zoom || 1) * factor);
  }

  const zoomScrub = {
    pointerId: -1,
    startX: 0,
    startY: 0,
    startZoom: 1,
    dragging: false,
  };

  function endZoomScrub() {
    zoomScrub.pointerId = -1;
    zoomScrub.dragging = false;
    document.body.classList.remove('lit-zoom-scrubbing');
    window.removeEventListener('pointermove', onZoomScrubMove, true);
    window.removeEventListener('pointerup', onZoomScrubUp, true);
    window.removeEventListener('pointercancel', onZoomScrubUp, true);
  }

  function onZoomReadoutPointerDown(e: PointerEvent) {
    if (e.button !== 0 || !workspace) return;
    if (e.ctrlKey) return;
    e.preventDefault();
    e.stopPropagation();
    zoomScrub.pointerId = e.pointerId;
    zoomScrub.startX = e.clientX;
    zoomScrub.startY = e.clientY;
    zoomScrub.startZoom = workspace.ui.zoom || 1;
    zoomScrub.dragging = false;
    window.removeEventListener('pointermove', onZoomScrubMove, true);
    window.removeEventListener('pointerup', onZoomScrubUp, true);
    window.removeEventListener('pointercancel', onZoomScrubUp, true);
    window.addEventListener('pointermove', onZoomScrubMove, true);
    window.addEventListener('pointerup', onZoomScrubUp, true);
    window.addEventListener('pointercancel', onZoomScrubUp, true);
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }

  function onZoomScrubMove(e: PointerEvent) {
    if (e.pointerId !== zoomScrub.pointerId || !workspace) return;
    const dx = e.clientX - zoomScrub.startX;
    const dy = e.clientY - zoomScrub.startY;
    if (!zoomScrub.dragging && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
    zoomScrub.dragging = true;
    document.body.classList.add('lit-zoom-scrubbing');
    e.preventDefault();
    const wrap = canvasWrapEl;
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    applyZoomAtClient(
      rect.left + rect.width / 2,
      rect.top + rect.height / 2,
      zoomFromPointerScrub(zoomScrub.startZoom, dx, dy)
    );
  }

  function onZoomScrubUp(e: PointerEvent) {
    if (e.pointerId !== zoomScrub.pointerId) return;
    endZoomScrub();
  }

  function onCanvasWheel(e: WheelEvent) {
    if (!workspace || !wheelShouldZoom(e)) return;
    e.preventDefault();
    e.stopPropagation();
    const oldZ = workspace.ui.zoom || 1;
    applyZoomAtClient(e.clientX, e.clientY, zoomFromWheelDelta(oldZ, e.deltaY, e.deltaMode));
  }

  $effect(() => {
    const el = canvasWrapEl;
    if (!el) return;
    // Chrome/Edge treat Ctrl+wheel as page zoom unless the listener is non-passive.
    el.addEventListener('wheel', onCanvasWheel, { passive: false, capture: true });
    return () => el.removeEventListener('wheel', onCanvasWheel, { capture: true });
  });

  function clearCanvasPanListeners() {
    window.removeEventListener('pointermove', onCanvasPanMove, true);
    window.removeEventListener('pointerup', onCanvasPanUp, true);
    window.removeEventListener('pointercancel', onCanvasPanUp, true);
    document.body.classList.remove('lit-canvas-panning');
  }

  function endCanvasPan() {
    canvasPan.pointerId = -1;
    panning = false;
    clearCanvasPanListeners();
  }

  const CTRL_PAN_SKIP_CLICK =
    '.project-editor, .template-editor, .confirm-backdrop, .confirm-dialog, .theme-dialog';
  const CTRL_PAN_SUPPRESS_EVENTS = ['click', 'auxclick', 'dblclick', 'mouseup', 'change'] as const;
  let ctrlPanClickHandler: ((ev: Event) => void) | null = null;
  let ctrlPanClickTimer: ReturnType<typeof setTimeout> | null = null;

  function clearCtrlPanClickSuppress() {
    if (ctrlPanClickHandler) {
      for (const type of CTRL_PAN_SUPPRESS_EVENTS) {
        window.removeEventListener(type, ctrlPanClickHandler, true);
      }
      ctrlPanClickHandler = null;
    }
    if (ctrlPanClickTimer != null) {
      clearTimeout(ctrlPanClickTimer);
      ctrlPanClickTimer = null;
    }
  }

  function suppressCtrlPanClicks() {
    if (ctrlPanClickTimer != null) {
      clearTimeout(ctrlPanClickTimer);
      ctrlPanClickTimer = null;
    }
    if (ctrlPanClickHandler) return;
    const handler = (ev: Event) => {
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
    };
    ctrlPanClickHandler = handler;
    for (const type of CTRL_PAN_SUPPRESS_EVENTS) {
      window.addEventListener(type, handler, true);
    }
  }

  function beginCanvasPan(e: PointerEvent) {
    if (!workspace) return;
    e.preventDefault();
    const cur = workspace.ui.viewport_scroll ?? defaultPan();
    canvasPan.pointerId = e.pointerId;
    canvasPan.startX = e.clientX;
    canvasPan.startY = e.clientY;
    canvasPan.origX = cur.x;
    canvasPan.origY = cur.y;
    panning = true;
    document.body.classList.add('lit-canvas-panning');
    clearCanvasPanListeners();
    window.addEventListener('pointermove', onCanvasPanMove, true);
    window.addEventListener('pointerup', onCanvasPanUp, true);
    window.addEventListener('pointercancel', onCanvasPanUp, true);
  }

  /** Ctrl+drag pans the canvas from anywhere, including over panels and controls. */
  function onCtrlCanvasPanDown(e: PointerEvent) {
    if (e.button !== 0 || !workspace || !e.ctrlKey) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.(CTRL_PAN_SKIP_CLICK)) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    canvasPan.swallowClicks = true;
    suppressCtrlPanClicks();
    beginCanvasPan(e);
    const cap = appShellEl || canvasWrapEl;
    if (cap) {
      try {
        cap.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }
  }

  $effect(() => {
    const el = appShellEl;
    if (!el) return;
    el.addEventListener('pointerdown', onCtrlCanvasPanDown, true);
    return () => el.removeEventListener('pointerdown', onCtrlCanvasPanDown, true);
  });

  function onCanvasPointerDown(e: PointerEvent) {
    if (e.button !== 0 || !workspace) return;
    if (e.ctrlKey) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('.panel')) return;
    if (t?.closest?.('.board-editor')) return;
    beginCanvasPan(e);
  }

  function onCanvasPanMove(e: PointerEvent) {
    if (canvasPan.pointerId !== e.pointerId || !workspace) return;
    e.preventDefault();
    const dx = e.clientX - canvasPan.startX;
    const dy = e.clientY - canvasPan.startY;
    updateWorkspace((ws) => {
      ws.ui.viewport_scroll = {
        x: canvasPan.origX + dx,
        y: canvasPan.origY + dy,
      };
    });
  }

  function onCanvasPanUp(e: PointerEvent) {
    if (canvasPan.pointerId !== e.pointerId) return;
    const cap = appShellEl || canvasWrapEl;
    if (cap?.hasPointerCapture?.(e.pointerId)) {
      try {
        cap.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }
    const swallow = canvasPan.swallowClicks;
    endCanvasPan();
    if (swallow) {
      suppressCtrlPanClicks();
      ctrlPanClickTimer = setTimeout(() => {
        canvasPan.swallowClicks = false;
        clearCtrlPanClickSuppress();
      }, 400);
    }
  }

  function visibleWorldOrigin(): { x: number; y: number } {
    return screenToWorld(pan, zoom || 1, { x: 0, y: 0 });
  }

  function maxZ(): number {
    if (!workspace?.panels.length) return 1;
    return Math.max(...workspace.panels.map((p) => p.z_index || 0));
  }

  function nowStamp(): string {
    return new Date().toISOString();
  }

  function stampPanel(p: Panel, when = nowStamp()) {
    p.updated_at = when;
  }

  function stampPanels(kind: Panel['kind'], itemId?: string, when = nowStamp()) {
    updateWorkspace((ws) => {
      for (const p of ws.panels) {
        if (p.kind !== kind) continue;
        if (itemId && p.item_id !== itemId) continue;
        stampPanel(p, when);
      }
    });
  }

  function focusPanel(id: string) {
    updateWorkspace((ws) => {
      const p = ws.panels.find((x) => x.id === id);
      if (!p) return;
      p.z_index = maxZ() + 1;
    });
  }

  function movePanel(id: string, patch: Partial<Panel>) {
    updateWorkspace((ws) => {
      const p = ws.panels.find((x) => x.id === id);
      if (!p) return;
      Object.assign(p, patch);
      stampPanel(p);
    });
  }

  function closePanel(id: string) {
    updateWorkspace((ws) => {
      ws.panels = ws.panels.filter((p) => p.id !== id);
    });
  }

  function itemLabel(item: Item): string {
    const key = String(item.fields[keyField()] ?? '').trim();
    const title = String(item.fields.title ?? '').trim();
    if (key && title) return `${key}  ${title}`;
    return key || title || 'this ticket';
  }

  function menuPosition(e: MouseEvent) {
    return {
      x: Math.min(e.clientX, window.innerWidth - 200),
      y: Math.min(e.clientY, window.innerHeight - 130),
    };
  }

  function specialPanelTitle(kind: Panel['kind']): string {
    if (kind === 'all_items') return 'All Items';
    if (kind === 'notes') return 'Project Notes';
    if (kind === 'deliverables') return 'Deliverables';
    return 'Panel';
  }

  function openItemContextMenu(e: MouseEvent, item: Item) {
    e.preventDefault();
    e.stopPropagation();
    boardEditor = null;
    itemDeleteConfirm = null;
    itemContextMenu = {
      itemId: item.id,
      name: itemLabel(item),
      ...menuPosition(e),
    };
  }

  function openPanelContextMenu(e: MouseEvent, panel: Panel) {
    e.preventDefault();
    e.stopPropagation();
    boardEditor = null;
    itemDeleteConfirm = null;
    itemContextMenu = {
      panelId: panel.id,
      name: specialPanelTitle(panel.kind),
      ...menuPosition(e),
    };
  }

  function zoomToPanel(panel: Panel) {
    const wrap = canvasWrapEl;
    if (!wrap) return;
    const view = focusView(
      {
        x: panel.x,
        y: panel.y,
        width: Math.max(1, panel.width),
        height: Math.max(1, panel.height),
      },
      { width: wrap.clientWidth, height: wrap.clientHeight },
      workspace?.ui.zoom || 1
    );
    updateWorkspace((ws) => {
      ws.ui.zoom = view.zoom;
      ws.ui.viewport_scroll = view.pan;
      const p = ws.panels.find((x) => x.id === panel.id);
      if (!p) return;
      p.z_index = Math.max(0, ...ws.panels.map((x) => x.z_index || 0)) + 1;
      p.collapsed = false;
    });
  }

  function focusItem(itemId: string) {
    itemContextMenu = null;
    if (!workspace) return;
    if (!workspace.panels.some((p) => p.kind === 'item' && p.item_id === itemId)) {
      openItemPanel(itemId);
    }
    const panel = workspace.panels.find((p) => p.kind === 'item' && p.item_id === itemId);
    if (!panel) return;
    zoomToPanel(panel);
  }

  function onAllItemsRowDblClick(e: MouseEvent, itemId: string) {
    if (e.ctrlKey || canvasPan.swallowClicks) return;
    e.preventDefault();
    e.stopPropagation();
    if (!workspace) return;
    const existing = workspace.panels.find((p) => p.kind === 'item' && p.item_id === itemId);
    if (existing) {
      zoomToPanel(existing);
      return;
    }
    openItemPanel(itemId);
  }

  function applyContextFocus() {
    const menu = itemContextMenu;
    itemContextMenu = null;
    if (!menu || !workspace) return;
    if (menu.itemId) {
      focusItem(menu.itemId);
      return;
    }
    if (menu.panelId) {
      const panel = workspace.panels.find((p) => p.id === menu.panelId);
      if (panel) zoomToPanel(panel);
    }
  }

  function askDeleteItemById(id: string, name: string) {
    itemContextMenu = null;
    itemDeleteConfirm = { id, name };
  }

  function stripItemLocally(itemId: string) {
    items = items.filter((i) => i.id !== itemId);
    if (itemSaveTimers[itemId]) {
      clearTimeout(itemSaveTimers[itemId]);
      delete itemSaveTimers[itemId];
    }
    const nextCache = { ...detailCache };
    delete nextCache[itemId];
    detailCache = nextCache;
    const drop = (ws: Workspace) => {
      const next = cloneWorkspace(ws);
      next.panels = (next.panels || []).filter((p) => p.item_id !== itemId);
      return next;
    };
    workspaces = workspaces.map(drop);
    if (workspace) {
      workspace = drop(workspace);
      scheduleWorkspaceSave();
    }
  }

  async function confirmDeleteItem() {
    if (!project || !itemDeleteConfirm) return;
    const id = itemDeleteConfirm.id;
    const slug = project.slug;
    itemDeleteConfirm = null;
    try {
      await api.deleteItem(slug, id);
      stripItemLocally(id);
      showToast('Ticket deleted');
    } catch (err) {
      showToast('Failed to delete ticket');
      console.error(err);
    }
  }

  function openItemPanel(itemId: string) {
    if (!workspace) return;
    const existing = workspace.panels.find((p) => p.kind === 'item' && p.item_id === itemId);
    if (existing) {
      focusPanel(existing.id);
      return;
    }
    void ensureDetail(itemId);
    const defaults = project?.default_item_panel || {};
    const panelW = Math.max(200, Number(defaults.width) || 720);
    const existingItem = detailCache[itemId] || items.find((i) => i.id === itemId);
    const headerEditor =
      !existingItem || !itemDescription(existingItem) ? HEADER_TITLE_EDITOR_PX : 0;
    const panelH = Math.max(
      minItemPanelHeight(bodyFieldRows) + headerEditor,
      Number(defaults.height) || 480
    );
    const origin = visibleWorldOrigin();
    updateWorkspace((ws) => {
      const z = Math.max(0, ...ws.panels.map((p) => p.z_index)) + 1;
      const stagger = (ws.panels.length % 5) * 30;
      ws.panels.push({
        id: `panel-item-${itemId.slice(0, 8)}-${Date.now().toString(36)}`,
        kind: 'item',
        item_id: itemId,
        x: snapToGrid(origin.x + 80 + stagger, ws.ui.zoom),
        y: snapToGrid(origin.y + 80 + stagger, ws.ui.zoom),
        width: panelW,
        height: panelH,
        z_index: z,
        collapsed: false,
        updated_at: existingItem?.updated_at || nowStamp(),
      });
    });
  }

  function openSpecial(kind: 'all_items' | 'notes' | 'deliverables') {
    if (!workspace) return;
    const existing = workspace.panels.find((p) => p.kind === kind);
    if (existing) {
      focusPanel(existing.id);
      return;
    }
    const sizes = {
      all_items: { w: 560, h: 640 },
      notes: { w: 400, h: 420 },
      deliverables: { w: 400, h: 360 },
    }[kind];
    const origin = visibleWorldOrigin();
    updateWorkspace((ws) => {
      ws.panels.push({
        id: `panel-${kind}-${Date.now().toString(36)}`,
        kind,
        x: snapToGrid(origin.x + 60, ws.ui.zoom),
        y: snapToGrid(origin.y + 60, ws.ui.zoom),
        width: sizes.w,
        height: sizes.h,
        z_index: maxZ() + 1,
        updated_at: nowStamp(),
      });
    });
  }

  async function createItem() {
    if (!project) return;
    try {
      const keys = items.map((it) => String(it.fields[keyField()] ?? ''));
      const item = await api.createItem(project.slug, {
        ticket_key: nextTicketKey(
          keys,
          project.ticket_prefix || readStoredPrefix(project.slug)
        ),
        title: '',
        priority: 88,
        urgency: 88,
        state: 'Submitted',
      });
      items = [...items, item];
      detailCache = { ...detailCache, [item.id]: item };
      openItemPanel(item.id);
      showToast('Item created');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Create failed');
    }
  }

  function visibleBodyFields(
    defs: FieldDef[],
    fields: Record<string, unknown>,
    itemId: string
  ): FieldDef[] {
    const slots = slotsToShow(extraTicketSlots[itemId], fields);
    return defs.filter((d) => {
      if (!isVisible(d, fields)) return false;
      if (!isExternalTicketId(d.id)) return true;
      const idx = ['external_ticket', 'external_ticket_2', 'external_ticket_3'].indexOf(d.id);
      return idx >= 0 && idx < slots;
    });
  }

  function canAddExternalTicket(
    shown: FieldDef[],
    rowDefs: FieldDef[],
    fields: Record<string, unknown>,
    itemId: string
  ): boolean {
    if (!rowDefs.some((d) => isExternalTicketId(d.id))) return false;
    if (!shown.some((d) => isExternalTicketId(d.id))) return false;
    return slotsToShow(extraTicketSlots[itemId], fields) < 3;
  }

  function revealExternalTicketSlot(itemId: string, fields: Record<string, unknown>) {
    extraTicketSlots = {
      ...extraTicketSlots,
      [itemId]: Math.min(3, slotsToShow(extraTicketSlots[itemId], fields) + 1),
    };
  }

  function patchItemFields(itemId: string, id: string, value: unknown) {
    const patch: Record<string, unknown> = { [id]: value };
    if (id === 'state' && value === 'Done') patch.waiting = false;
    if (id === 'waiting' && value === true) {
      const current = detailCache[itemId];
      if (!current?.fields?.waiting_since) patch.waiting_since = todayLocalDate();
    }
    scheduleItemPatch(itemId, patch);
  }

  function scheduleItemPatch(itemId: string, fields: Record<string, unknown>) {
    if (!project) return;
    // Optimistic lean list update
    const touched = nowStamp();
    items = items.map((it) =>
      it.id === itemId ? { ...it, fields: { ...it.fields, ...fields }, updated_at: touched } : it
    );
    stampPanels('item', itemId, touched);
    if (detailCache[itemId]) {
      detailCache = {
        ...detailCache,
        [itemId]: {
          ...detailCache[itemId],
          fields: { ...detailCache[itemId].fields, ...fields },
        },
      };
    }
    if (itemSaveTimers[itemId]) clearTimeout(itemSaveTimers[itemId]);
    itemSaveTimers[itemId] = setTimeout(async () => {
      try {
        const current = detailCache[itemId] || items.find((i) => i.id === itemId);
        const version = current?.version;
        const updated = await api.patchItem(project!.slug, itemId, fields, version);
        items = items.map((it) => {
          if (it.id !== itemId) return it;
          // lean merge: omit textarea/richtext from list store but keep others
          const leanFields = { ...it.fields };
          for (const [k, v] of Object.entries(updated.fields)) {
            const def = fieldDefs.find((f) => f.id === k);
            if (def && (def.type === 'richtext' || def.type === 'textarea')) continue;
            leanFields[k] = v;
          }
          return { ...it, fields: leanFields, version: updated.version, waiting: updated.waiting, updated_at: updated.updated_at };
        });
        detailCache = { ...detailCache, [itemId]: updated };
      } catch (e) {
        showToast('Save failed — reloading item');
        console.error(e);
        if (project) {
          const full = await api.item(project.slug, itemId);
          detailCache = { ...detailCache, [itemId]: full };
          items = await api.items(project.slug);
        }
      }
    }, 350);
  }

  function keyField(): string {
    return project?.primary_identifier_field || 'ticket_key';
  }

  /** Ticket number + description live in the header editor, not the panel body. */
  function isHeaderManagedField(f: { id: string }): boolean {
    return f.id === 'title' || f.id === keyField();
  }

  function headerEditLabel(id: string, fallback: string): string {
    const lab = fieldDefs.find((f) => f.id === id)?.label;
    if (id === 'ticket_key' && (!lab || lab === 'Ticket Key')) return 'Ticket number';
    if (id === 'title' && (!lab || lab === 'Title')) return 'Description';
    return lab || fallback;
  }

  function primaryId(item: Item): string {
    const v = String(item.fields[keyField()] ?? '').trim();
    if (v) return v;
    return 'Untitled';
  }

  function itemDescription(item: Item): string {
    return String(item.fields.title ?? '').trim();
  }

  function itemHeading(item: Item): string {
    const desc = itemDescription(item);
    return desc ? `${primaryId(item)}  ${desc}` : primaryId(item);
  }

  function itemForPanel(p: Panel): Item | null {
    if (!p.item_id) return null;
    return detailCache[p.item_id] || items.find((i) => i.id === p.item_id) || null;
  }

  function showToast(msg: string) {
    toast = msg;
    setTimeout(() => {
      if (toast === msg) toast = null;
    }, 2800);
  }

  function setFilterOption(fieldId: string, option: string | boolean, checked: boolean) {
    updateWorkspace((ws) => {
      const cur = (ws.filters.active[fieldId] as Array<string | boolean> | undefined) || [];
      let next = [...cur];
      if (checked && !next.includes(option)) next.push(option);
      if (!checked) next = next.filter((x) => x !== option);
      if (next.length === 0) delete ws.filters.active[fieldId];
      else ws.filters.active[fieldId] = next;
    });
  }

  function applyPreset(presetId: string) {
    updateWorkspace((ws) => {
      const p = ws.filters.presets.find((x) => x.id === presetId);
      if (p) ws.filters.active = structuredClone(p.filter);
    });
  }

  function clickListSort(field: string) {
    updateWorkspace((ws) => {
      if (!ws.sort) ws.sort = { field, direction: 'asc' };
      else if (ws.sort.field === field) {
        ws.sort.direction = ws.sort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        ws.sort.field = field;
        ws.sort.direction = 'asc';
      }
    });
  }

  function listSortMark(field: string): string {
    if (workspace?.sort?.field !== field) return '';
    return workspace.sort.direction === 'desc' ? ' ▼' : ' ▲';
  }

  function formatItemUpdatedDate(iso: string | undefined): string {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
    return todayLocalDate(d);
  }

  function clearFilters() {
    updateWorkspace((ws) => {
      ws.filters.active = {};
    });
  }

  async function saveNotes(content: unknown) {
    if (!project) return;
    notesContent = content;
    try {
      await api.putNotes(project.slug, content);
      stampPanels('notes');
    } catch {
      showToast('Notes save failed');
    }
  }

  async function saveDeliverables(next: Array<Record<string, unknown>>) {
    if (!project) return;
    deliverables = next;
    try {
      await api.putDeliverables(project.slug, next);
      stampPanels('deliverables');
    } catch {
      showToast('Deliverables save failed');
    }
  }

  function addDeliverable() {
    const next = [
      ...deliverables,
      { id: crypto.randomUUID(), title: '', done: false, notes: '' },
    ];
    void saveDeliverables(next);
  }

  function sortOpenPanels() {
    if (!workspace) return;
    const wrap = canvasWrapEl;
    if (!wrap) return;
    const z = zoom || 1;
    const origin = visibleWorldOrigin();
    const viewH = wrap.clientHeight / z;
    const ordered = sortItemPanels(workspace.panels, itemForPanel, sortBy, fieldDefs);
    const placed = layoutColumnMajor(ordered, origin, viewH);
    const byId = new Map(placed.map((p) => [p.id, p]));
    updateWorkspace((ws) => {
      ws.sort = { field: sortBy, direction: 'asc' };
      ws.panels = ws.panels.map((p) => {
        const n = byId.get(p.id);
        return n ? { ...p, x: snapToGrid(n.x, z), y: snapToGrid(n.y, z) } : p;
      });
    });
  }

  function seeAll() {
    if (!workspace) return;
    const wrap = canvasWrapEl;
    if (!wrap) return;
    if (!workspace.panels.length) {
      showToast('No panels on this board');
      return;
    }
    const bounds = panelsWorldBounds(workspace.panels);
    if (!bounds) return;
    const view = fitView(bounds, { width: wrap.clientWidth, height: wrap.clientHeight });
    updateWorkspace((ws) => {
      ws.ui.zoom = view.zoom;
      ws.ui.viewport_scroll = view.pan;
    });
  }

  async function newWorkspace() {
    if (!project) return;
    // Save current board into the list (and debounce server save) before leaving
    flushCurrentWorkspaceToList();
    scheduleWorkspaceSave();
    try {
      const maxOrder = Math.max(0, ...workspaces.map((w) => w.order ?? 0));
      const w = await api.createWorkspace(
        project.slug,
        `Board ${workspaces.filter((x) => !isMainBoard(x)).length + 1}`,
        maxOrder + 1
      );
      workspaces = sortWorkspaces([...workspaces, cloneWorkspace(w)]);
      workspace = cloneWorkspace(w);
      updateWorkspace((ws) => {
        ws.ui.theme = committedThemeId;
        ws.ui.transparent_panels = transparentPanels;
      });
      void rememberLastWorkspace(w.id);
    } catch (e) {
      showToast('Failed to create workspace');
      console.error(e);
    }
  }

  function openBoardEditor(e: MouseEvent, w: Workspace) {
    e.preventDefault();
    e.stopPropagation();
    boardEditor = {
      id: w.id,
      name: w.name,
      tab_color: w.tab_color ?? null,
      x: Math.min(e.clientX, window.innerWidth - 240),
      y: Math.min(e.clientY, window.innerHeight - 200),
    };
  }

  async function saveBoardEditor() {
    if (!project || !boardEditor) return;
    const id = boardEditor.id;
    const name = boardEditor.name.trim() || 'Untitled board';
    const tab_color = boardEditor.tab_color;
    const existing = workspaces.find((w) => w.id === id);
    if (!existing) {
      boardEditor = null;
      return;
    }
    const next = cloneWorkspace(existing);
    next.name = name;
    next.tab_color = tab_color;
    workspaces = sortWorkspaces(workspaces.map((w) => (w.id === id ? next : w)));
    if (workspace?.id === id) {
      workspace = { ...cloneWorkspace(workspace), name, tab_color };
    }
    boardEditor = null;
    try {
      const saved = await api.putWorkspace(project.slug, id, next);
      workspaces = sortWorkspaces(workspaces.map((w) => (w.id === id ? saved : w)));
      if (workspace?.id === id) {
        workspace = cloneWorkspace(saved);
      }
      showToast('Board updated');
    } catch (err) {
      showToast('Failed to update board');
      console.error(err);
    }
  }

  function askRemoveBoard() {
    if (!project || !boardEditor) return;
    const id = boardEditor.id;
    const name = boardEditor.name.trim() || 'this board';
    if (id === 'ws-main') {
      showToast('Main Board cannot be removed');
      return;
    }
    if (workspaces.length <= 1) {
      showToast('Cannot remove the last board');
      return;
    }
    boardRemoveConfirm = { id, name };
    boardEditor = null;
  }

  async function confirmRemoveBoard() {
    if (!project || !boardRemoveConfirm) return;
    const id = boardRemoveConfirm.id;
    const slug = project.slug;
    if (id === 'ws-main') {
      showToast('Main Board cannot be removed');
      boardRemoveConfirm = null;
      return;
    }
    const remaining = sortWorkspaces(workspaces.filter((w) => w.id !== id));
    if (!remaining.length) {
      showToast('Cannot remove the last board');
      boardRemoveConfirm = null;
      return;
    }

    // Drop a pending save of the deleted board so it cannot be written back.
    if (saveTimer && workspace?.id === id) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }

    const wasCurrent = workspace?.id === id;
    workspaces = remaining;
    boardRemoveConfirm = null;
    boardEditor = null;

    // Switch locally — do not call selectWorkspace, which flushes the
    // still-in-memory deleted board back into the tab list.
    if (wasCurrent) {
      const next = remaining[0];
      workspace = cloneWorkspace(next);
      if (workspace.sort?.field && isPanelSortField(workspace.sort.field)) {
        sortBy = workspace.sort.field;
      }
      applyBoardAppearance(workspace);
      void rememberLastWorkspace(next.id);
    }

    try {
      await api.deleteWorkspace(slug, id);
      showToast('Board removed');
    } catch (err) {
      showToast('Failed to remove board');
      console.error(err);
    }
  }

  async function openProjectFolder() {
    if (!project?.data_path) {
      showToast('Project folder is not available');
      return;
    }
    try {
      await api.openProjectFolder(project.slug);
    } catch (err) {
      showToast('Could not open folder');
      console.error(err);
    }
  }

  function openProjectEditor() {
    if (!project) return;
    if (projectEditor) {
      void closeProjectEditor(true);
      return;
    }
    projectEditor = {
      name: project.name,
      ticket_prefix: project.ticket_prefix || readStoredPrefix(project.slug) || 'NEW-',
      url_prefix: String(project.url_prefix ?? ''),
      newName: '',
      newPrefix: 'NEW-',
      newTemplate: 'issue-tracker',
      templates: [],
    };
    void api.templates().then((body) => {
      if (!projectEditor) return;
      projectEditor = {
        ...projectEditor,
        templates: body.templates,
        newTemplate: body.default || 'issue-tracker',
      };
    });
  }

  function openTemplateEditor() {
    void closeProjectEditor(true);
    templateEditorOpen = true;
  }

  async function persistProjectMeta(name: string, prefixRaw: string, urlPrefixRaw: string, toast: boolean) {
    if (!project) return false;
    const trimmed = name.trim();
    if (!trimmed) {
      if (toast) showToast('Project name is required');
      return false;
    }
    const ticket_prefix = normalizeTicketPrefix(prefixRaw);
    const url_prefix = String(urlPrefixRaw ?? '').trim();
    writeStoredPrefix(project.slug, ticket_prefix);
    try {
      await api.patchSettings({ ticket_prefix_by_project: { [project.slug]: ticket_prefix } });
      const saved = await api.patchProject(project.slug, { name: trimmed, ticket_prefix, url_prefix });
      project = {
        ...saved,
        ticket_prefix: saved.ticket_prefix || ticket_prefix,
        url_prefix: saved.url_prefix ?? url_prefix,
      };
      writeStoredPrefix(project.slug, project.ticket_prefix || ticket_prefix);
      projects = projects.map((p) => (p.slug === saved.slug ? project! : p));
      if (toast) showToast('Project updated');
      return true;
    } catch (err) {
      if (toast) showToast('Failed to update project');
      console.error(err);
      return false;
    }
  }

  async function saveProjectEditor() {
    if (!project || !projectEditor) return;
    const ok = await persistProjectMeta(
      projectEditor.name,
      projectEditor.ticket_prefix,
      projectEditor.url_prefix,
      true
    );
    if (ok && projectEditor) {
      projectEditor = {
        ...projectEditor,
        name: project.name,
        ticket_prefix: project.ticket_prefix || projectEditor.ticket_prefix,
        url_prefix: String(project.url_prefix ?? projectEditor.url_prefix),
      };
    }
  }

  async function closeProjectEditor(save: boolean) {
    const ed = projectEditor;
    if (!ed) return;
    projectEditor = null;
    if (save) await persistProjectMeta(ed.name, ed.ticket_prefix, ed.url_prefix, false);
  }

  async function switchProject(slug: string) {
    if (projectEditor) await closeProjectEditor(true);
    if (!project || slug === project.slug) return;
    await loadProject(slug);
  }

  async function createNewProject() {
    if (!projectEditor) return;
    const name = projectEditor.newName.trim();
    if (!name) {
      showToast('New project needs a name');
      return;
    }
    const ticket_prefix = normalizeTicketPrefix(projectEditor.newPrefix);
    const slug = uniqueSlug(
      slugFromName(name),
      projects.map((p) => p.slug)
    );
    try {
      const created = await api.createProject({
        slug,
        name,
        ticket_prefix,
        template: projectEditor.newTemplate || undefined,
      });
      projects = [...projects, created];
      projectEditor = null;
      await loadProject(created.slug);
      showToast('Project created');
    } catch (err) {
      showToast('Failed to create project');
      console.error(err);
    }
  }

  function tabStyle(w: Workspace): string {
    const c = w.tab_color;
    if (!c) return '';
    if (w.id === workspace?.id) {
      return `background:${c}33;border-color:${c};color:var(--text)`;
    }
    return `background:${c}22;border-color:${c}88;color:var(--text)`;
  }
</script>

{#if loading}
  <div class="empty-hint" style="padding-top:20vh">Loading Local Issue Tracker…</div>
{:else if error}
  <div class="empty-hint" style="padding-top:20vh;color:var(--danger)">{error}</div>
{:else if project && workspace}
  <div class="app-shell" bind:this={appShellEl}>
    <header class="topbar">
      <button
        type="button"
        class="brand"
        title="Project settings — name, ticket prefix, switch or create"
        onclick={openProjectEditor}
      >
        <div class="brand-mark"></div>
        {project.name}
      </button>
      <button type="button" class="ghost" title="Toggle sidebar (⌘\)" onclick={toggleSidebar}>
        {sidebarVisible ? 'Hide tabs' : 'Show tabs'}
      </button>
      <button type="button" class="primary" onclick={createItem}>+ Item</button>
      <button type="button" onclick={() => openSpecial('all_items')}>All Items</button>
      <button type="button" onclick={() => openSpecial('notes')}>Notes</button>
      <button type="button" onclick={() => openSpecial('deliverables')}>Deliverables</button>
      <div class="sort-controls">
        <select
          style="width:auto;min-width:140px"
          value={sortBy}
          onchange={(e) => {
            const v = e.currentTarget.value;
            if (isPanelSortField(v)) sortBy = v;
          }}
          title="Sort open item panels by"
        >
          {#each PANEL_SORT_OPTIONS as opt}
            <option value={opt.id}>{opt.label}</option>
          {/each}
        </select>
        <button type="button" onclick={sortOpenPanels} title="Line up panels top-to-bottom, then left-to-right">
          Sort
        </button>
      </div>
      <button type="button" onclick={seeAll} title="Zoom to fit every panel on this board">
        See All
      </button>
      <button type="button" onclick={() => zoomByKeyboard(0)} title="Reset zoom to 100%">
        100%
      </button>
      <div class="theme-controls">
        <button
          type="button"
          class="theme-select"
          aria-haspopup="dialog"
          aria-expanded={themeMenuOpen}
          title="Themes"
          onclick={() => {
            if (!themeMenuOpen) openThemeMenu();
          }}
        >
          {THEMES.find((t) => t.id === (themeMenuOpen ? themeId : committedThemeId))?.name ?? 'Theme'}
        </button>
        {#if themeMenuOpen}
          <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
          <div
            class="theme-dialog"
            role="dialog"
            tabindex="-1"
            aria-label="Themes"
            onclick={(e) => e.stopPropagation()}
          >
            <div class="theme-dialog-head">
              <div class="board-editor-title" style="margin:0">Themes</div>
              <button
                type="button"
                class="ghost theme-dialog-close"
                title="Close"
                onclick={() => closeThemeMenu(true)}
              >✕</button>
            </div>
            <label
              class="theme-transparent"
              title="See through panel fill — no wallpaper painted in the card"
            >
              <input
                type="checkbox"
                checked={transparentPanels}
                onchange={(e) => void setTransparentPanels(e.currentTarget.checked)}
              />
              Transparent
            </label>
            {#if transparentPanels}
              <label
                class="theme-transparency"
                title="How see-through the panel fill is for this theme"
              >
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={Math.round(panelTransparency * 100)}
                  oninput={(e) => setPanelTransparency(Number(e.currentTarget.value) / 100)}
                />
                <span class="theme-transparency-val">{Math.round(panelTransparency * 100)}%</span>
              </label>
            {/if}
            <ul class="theme-menu" role="listbox" aria-label="Theme">
              {#each THEMES as t, i}
                <li
                  role="option"
                  data-theme-id={t.id}
                  aria-selected={t.id === committedThemeId}
                  class:active={t.id === highlightedThemeId}
                  onpointerdown={() => previewTheme(t.id)}
                  ondblclick={() => void setTheme(t.id)}
                >
                  <span class="theme-num">{i + 1}</span>
                  {t.name}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
      <div class="topbar-spacer"></div>
      <div class="topbar-meta">
        {workspace.name} ·
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span
          class="zoom-readout"
          title="Drag to zoom. Double-click to reset to 100%"
          onpointerdown={onZoomReadoutPointerDown}
          ondblclick={() => zoomByKeyboard(0)}
        >zoom {(zoom * 100).toFixed(0)}%</span>
        · scroll to zoom
        {#if compact}<span class="chip">compact</span>{/if}
        <span class="build-stamp" title="UI build id — if this is missing, hard-refresh">ui:2026-08-29a</span>
        <span
          class="server-dot"
          class:ok={serverOk}
          class:down={!serverOk}
          title={serverOk ? 'Connected to server' : 'Server disconnected'}
          aria-label={serverOk ? 'Connected to server' : 'Server disconnected'}
        ></span>
      </div>
    </header>

    <aside class="sidebar" class:hidden={!sidebarVisible}>
      {#each workspaces as w (w.id)}
        <button
          type="button"
          class="ws-tab"
          data-ws-id={w.id}
          class:active={w.id === workspace.id}
          class:ws-tab-main={isMainBoard(w)}
          class:ws-tab-dragging={dragWsId === w.id}
          style={tabStyle(w)}
          onclick={() => onTabClick(w.id)}
          onpointerdown={(e) => onTabPointerDown(e, w.id)}
          ondblclick={(e) => openBoardEditor(e, w)}
          oncontextmenu={(e) => openBoardEditor(e, w)}
          title={`${w.name} — click to open; drag to reorder; right-click or double-click to rename / set colour`}
        >
          {w.name}
        </button>
      {/each}
      <button type="button" class="ws-tab ws-tab-add" onclick={() => void newWorkspace()} title="New workspace">+</button>
    </aside>

    {#if projectEditor}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="project-editor" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <div class="board-editor-title">Project</div>

        <section class="project-section">
          <div class="project-section-title">This project</div>
          <label class="field-label" for="project-name-input">Name</label>
          <input
            id="project-name-input"
            type="text"
            bind:value={projectEditor.name}
            onkeydown={(e) => {
              if (e.key === 'Enter') void saveProjectEditor();
              if (e.key === 'Escape') projectEditor = null;
            }}
          />
          <label class="field-label" for="project-prefix-input" style="margin-top:10px">Ticket prefix</label>
          <input
            id="project-prefix-input"
            type="text"
            bind:value={projectEditor.ticket_prefix}
            placeholder="NEW-"
            onkeydown={(e) => {
              if (e.key === 'Enter') void saveProjectEditor();
              if (e.key === 'Escape') projectEditor = null;
            }}
          />
          <label class="field-label" for="project-url-prefix-input" style="margin-top:10px">URL prefix</label>
          <input
            id="project-url-prefix-input"
            type="text"
            bind:value={projectEditor.url_prefix}
            placeholder="https://example.com/browse/"
            onkeydown={(e) => {
              if (e.key === 'Enter') void saveProjectEditor();
              if (e.key === 'Escape') projectEditor = null;
            }}
          />
          <div class="board-editor-actions">
            <button type="button" class="ghost" onclick={() => void closeProjectEditor(false)}>Cancel</button>
            <button type="button" onclick={openTemplateEditor}>Templates</button>
            <button type="button" class="primary" onclick={() => void saveProjectEditor()}>Save</button>
          </div>
        </section>

        <section class="project-section">
          <div class="project-section-title">Open project</div>
          <div class="project-list">
            {#each projects as p}
              <button
                type="button"
                class:current={p.slug === project.slug}
                onclick={() => void switchProject(p.slug)}
              >
                {p.name}
              </button>
            {/each}
          </div>
        </section>

        <section class="project-section">
          <div class="project-section-title">New project</div>
          <input
            type="text"
            placeholder="Name"
            bind:value={projectEditor.newName}
            onkeydown={(e) => {
              if (e.key === 'Enter') void createNewProject();
            }}
          />
          <input
            type="text"
            placeholder="Ticket prefix (NEW-)"
            style="margin-top:6px"
            bind:value={projectEditor.newPrefix}
            onkeydown={(e) => {
              if (e.key === 'Enter') void createNewProject();
            }}
          />
          {#if projectEditor.templates.length}
            <label class="field-label" for="new-project-template" style="margin-top:8px">Template</label>
            <select id="new-project-template" bind:value={projectEditor.newTemplate}>
              {#each projectEditor.templates as t}
                <option value={t.id}>{t.name}{t.is_default ? ' (default)' : ''}</option>
              {/each}
            </select>
          {/if}
          <div class="board-editor-actions">
            <button type="button" class="primary" onclick={() => void createNewProject()}>Create</button>
          </div>
        </section>

        <section class="project-section">
          <div class="project-section-title">Location on disk</div>
          <div class="project-path-row">
            <div class="project-path" title={project.data_path || ''}>{project.data_path || '—'}</div>
            <button
              type="button"
              title="Open this folder in File Explorer"
              disabled={!project.data_path}
              onclick={() => void openProjectFolder()}
            >Open</button>
          </div>
        </section>
      </div>
    {/if}

    {#if templateEditorOpen && project}
      <TemplateEditor
        projectSlug={project.slug}
        projectName={project.name}
        onclose={() => (templateEditorOpen = false)}
        onprojectfields={(doc) => {
          fieldsDoc = doc;
        }}
      />
    {/if}

    {#if boardEditor}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="board-editor"
        style:left="{boardEditor.x}px"
        style:top="{boardEditor.y}px"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => e.stopPropagation()}
      >
        <div class="board-editor-title">Board settings</div>
        <label class="field-label" for="board-name-input">Name</label>
        <input
          id="board-name-input"
          type="text"
          bind:value={boardEditor.name}
          onkeydown={(e) => {
            if (e.key === 'Enter') void saveBoardEditor();
            if (e.key === 'Escape') boardEditor = null;
          }}
        />
        <div class="field-label" style="margin-top:10px">Tab colour</div>
        <div class="color-swatches">
          {#each TAB_COLOR_SWATCHES as c}
            <button
              type="button"
              class="color-swatch"
              class:selected={(boardEditor.tab_color || null) === c}
              class:swatch-none={c === null}
              style:background={c || 'transparent'}
              title={c || 'Default'}
              onclick={() => {
                if (boardEditor) boardEditor = { ...boardEditor, tab_color: c };
              }}
            ></button>
          {/each}
        </div>
        <div class="board-editor-actions">
          {#if boardEditor.id !== 'ws-main'}
            <button type="button" class="danger" onclick={() => askRemoveBoard()}>Remove</button>
          {/if}
          <span class="board-editor-actions-spacer"></span>
          <button type="button" class="ghost" onclick={() => (boardEditor = null)}>Cancel</button>
          <button type="button" class="primary" onclick={() => void saveBoardEditor()}>Save</button>
        </div>
      </div>
    {/if}

    {#if itemContextMenu}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="item-context-menu"
        style:left="{itemContextMenu.x}px"
        style:top="{itemContextMenu.y}px"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onclick={() => applyContextFocus()}
        >Focus</button>
        {#if itemContextMenu.itemId}
          <button
            type="button"
            class="danger"
            onclick={() => {
              if (!itemContextMenu?.itemId) return;
              askDeleteItemById(itemContextMenu.itemId, itemContextMenu.name);
            }}
          >Delete ticket</button>
        {/if}
      </div>
    {/if}

    {#if itemDeleteConfirm}
      <div class="confirm-backdrop" role="presentation">
        <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
        <div
          class="confirm-dialog"
          role="alertdialog"
          tabindex="-1"
          aria-modal="true"
          aria-labelledby="item-delete-title"
          aria-describedby="item-delete-desc"
          onclick={(e) => e.stopPropagation()}
        >
          <div class="board-editor-title" id="item-delete-title">Delete ticket</div>
          <p class="confirm-dialog-body" id="item-delete-desc">
            Delete <span class="confirm-dialog-name">{itemDeleteConfirm.name}</span>? This cannot
            be undone.
          </p>
          <div class="board-editor-actions">
            <button type="button" class="ghost" onclick={() => (itemDeleteConfirm = null)}>Cancel</button>
            <button type="button" class="danger" onclick={() => void confirmDeleteItem()}>Delete</button>
          </div>
        </div>
      </div>
    {/if}

    {#if boardRemoveConfirm}
      <div class="confirm-backdrop" role="presentation">
        <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
        <div
          class="confirm-dialog"
          role="alertdialog"
          tabindex="-1"
          aria-modal="true"
          aria-labelledby="board-remove-title"
          aria-describedby="board-remove-desc"
          onclick={(e) => e.stopPropagation()}
        >
          <div class="board-editor-title" id="board-remove-title">Remove board</div>
          <p class="confirm-dialog-body" id="board-remove-desc">
            Remove <span class="confirm-dialog-name">{boardRemoveConfirm.name}</span> from this
            project? This cannot be undone.
          </p>
          <div class="board-editor-actions">
            <button type="button" class="ghost" onclick={() => (boardRemoveConfirm = null)}>Cancel</button>
            <button type="button" class="danger" onclick={() => void confirmRemoveBoard()}>Remove</button>
          </div>
        </div>
      </div>
    {/if}

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="canvas-wrap"
      role="application"
      aria-label="Unlimited workspace. Drag empty space to pan. Ctrl+drag pans even over panels. Scroll or Ctrl+scroll zooms toward the pointer."
      bind:this={canvasWrapEl}
      class:is-panning={panning}
      style:--zoom={zoom}
      onpointerdown={onCanvasPointerDown}
    >
      <div class="canvas" style:transform={`translate(${pan.x}px, ${pan.y}px) scale(${zoom})`}>
        {#each workspace.panels as panel (panel.id)}
          {@const item = itemForPanel(panel)}
          {@const colors =
            panel.kind === 'item' && item
              ? panelColors(item.fields, project.color_coding)
              : { bg: '', border: '' }}

          <FloatingPanel
            {panel}
            {zoom}
            active={false}
            title={
              panel.kind === 'item'
                ? item
                  ? itemHeading(item)
                  : 'Item'
                : panel.kind === 'all_items'
                  ? 'All Items'
                  : panel.kind === 'notes'
                    ? 'Project Notes'
                    : 'Deliverables'
            }
            accentBg={transparentPanels ? undefined : colors.bg || undefined}
            accentBorder={colors.border || undefined}
            compact={compact}
            fillBody={panel.kind === 'item' || panel.kind === 'notes'}
            onfocus={() => focusPanel(panel.id)}
            onfocusview={() => zoomToPanel(panel)}
            onmove={(patch) => movePanel(panel.id, patch)}
            onclose={() => closePanel(panel.id)}
            oncontext={
              panel.kind === 'item' && item
                ? (e) => openItemContextMenu(e, item)
                : (e) => openPanelContextMenu(e, panel)
            }
          >
            {#snippet titleSlot()}
              {#if panel.kind === 'item' && item && !compact}
                <ItemTitleBar
                  ticketKey={String(item.fields[keyField()] ?? '')}
                  description={String(item.fields.title ?? '')}
                  keyFieldLabel={headerEditLabel(keyField(), 'Ticket number')}
                  descriptionLabel={headerEditLabel('title', 'Description')}
                  ticketLaunchHref={ticketHref(
                    project.url_prefix,
                    String(item.fields[keyField()] ?? '')
                  )}
                  onTicketKey={(value) => scheduleItemPatch(item.id, { [keyField()]: value })}
                  onDescription={(value) => scheduleItemPatch(item.id, { title: value })}
                />
              {:else}
                <div class="panel-title">
                  {panel.kind === 'item'
                    ? item
                      ? compact
                        ? primaryId(item)
                        : itemHeading(item)
                      : 'Item'
                    : panel.kind === 'all_items'
                      ? 'All Items'
                      : panel.kind === 'notes'
                        ? 'Project Notes'
                        : 'Deliverables'}
                </div>
              {/if}
            {/snippet}
            {#snippet compactChildren()}
              <div class="compact-id">{panel.kind === 'item' ? (item ? primaryId(item) : '…') : panel.kind === 'all_items' ? 'All Items' : panel.kind === 'notes' ? 'Notes' : 'Deliverables'}</div>
            {/snippet}

            {#if panel.kind === 'item' && item}
              {#if item.waiting?.is_waiting}
                <div class="waiting-badge" style="margin-bottom:8px">
                  ⏱ Waiting
                  {formatWaitingDays(
                    liveSeconds(item.waiting.current_started_at, nowTick) ??
                      item.waiting.current_seconds
                  )}
                </div>
              {/if}
              {#if !detailCache[item.id]}
                <div class="empty-hint">Loading item…</div>
              {:else}
                {#key item.id}
                  {#each bodyFieldBlocks as block, bi (block.kind === 'waiting' ? 'waiting' : block.row.row)}
                    {#if block.kind === 'waiting'}
                      {@const person = pickField(block.fields, 'waiting_for')}
                      {@const since = pickField(block.fields, 'waiting_since')}
                      {@const waitingOn = Boolean(detailCache[item.id].fields.waiting)}
                      {#if detailCache[item.id].fields.state !== 'Done'}
                      <div class="waiting-block">
                        <label class="check-row">
                          <input
                            type="checkbox"
                            checked={waitingOn}
                            onchange={(e) => patchItemFields(item.id, 'waiting', e.currentTarget.checked)}
                          />
                          Waiting for...
                        </label>
                        {#if waitingOn}
                          <div class="waiting-details">
                            {#if person}
                              <label class="waiting-inline">
                                <span>{person.label || 'Name'}:</span>
                                <select
                                  value={String(detailCache[item.id].fields.waiting_for ?? '')}
                                  onchange={(e) =>
                                    scheduleItemPatch(item.id, { waiting_for: e.currentTarget.value })}
                                >
                                  <option value=""></option>
                                  {#each waitingNameChoices(person.options, detailCache[item.id].fields.waiting_for) as opt}
                                    <option value={opt}>{opt}</option>
                                  {/each}
                                </select>
                              </label>
                            {/if}
                            {#if since}
                              <label class="waiting-inline">
                                <span>Since:</span>
                                <input
                                  type="date"
                                  value={String(detailCache[item.id].fields.waiting_since ?? '')}
                                  oninput={(e) =>
                                    scheduleItemPatch(item.id, { waiting_since: e.currentTarget.value })}
                                  onchange={(e) =>
                                    scheduleItemPatch(item.id, { waiting_since: e.currentTarget.value })}
                                />
                              </label>
                            {/if}
                          </div>
                        {/if}
                      </div>
                      {/if}
                    {:else}
                      {@const shown = visibleBodyFields(
                        block.row.fields,
                        detailCache[item.id].fields,
                        item.id
                      )}
                      {@const addUrl = canAddExternalTicket(
                        shown,
                        block.row.fields,
                        detailCache[item.id].fields,
                        item.id
                      )}
                      {#if shown.length}
                      <div
                        class="field-row"
                        class:field-row-multi={shown.length > 1}
                        class:field-row-fill={isNotesFillRow({ row: block.row.row, fields: shown })}
                      >
                        {#each shown as def, di (def.id)}
                          <div class="field-col" style:flex={`${fieldFlex(def, shown)} 1 0`}>
                            <FieldRenderer
                              {def}
                              fill={isNotesFillRow({ row: block.row.row, fields: shown })}
                              fields={detailCache[item.id].fields}
                              addSlot={addUrl &&
                                di === shown.length - 1 &&
                                isExternalTicketId(def.id)}
                              onAddSlot={() =>
                                revealExternalTicketSlot(item.id, detailCache[item.id].fields)}
                              onchange={(id, value) => patchItemFields(item.id, id, value)}
                            />
                          </div>
                        {/each}
                      </div>
                      {/if}
                    {/if}
                  {/each}
                {/key}
              {/if}
            {:else if panel.kind === 'all_items'}
              <div class="toolbar-row">
                <button type="button" class="primary" onclick={createItem}>New item</button>
                <button type="button" class="ghost" onclick={clearFilters}>Clear filters</button>
                {#each workspace.filters.presets as preset}
                  <button type="button" onclick={() => applyPreset(preset.id)}>{preset.name}</button>
                {/each}
              </div>

              {#if filterableFields.length}
                {#snippet filterGroup(ff: FieldDef)}
                  <div class="filter-group">
                    <div class="filter-group-title">{ff.label}</div>
                    {#if ff.type === 'select' && ff.options}
                      {#each filterCheckboxOptions(ff) as opt}
                        <label class="check-row">
                          <input
                            type="checkbox"
                            checked={((workspace.filters.active[ff.id] as string[]) || []).includes(opt)}
                            onchange={(e) => setFilterOption(ff.id, opt, e.currentTarget.checked)}
                          />
                          {opt}
                        </label>
                      {/each}
                    {:else if ff.type === 'checkbox'}
                      <label class="check-row">
                        <input
                          type="checkbox"
                          checked={((workspace.filters.active[ff.id] as boolean[]) || []).includes(true)}
                          onchange={(e) => setFilterOption(ff.id, true, e.currentTarget.checked)}
                        />
                        Yes
                      </label>
                    {/if}
                  </div>
                {/snippet}
                <div class="filter-panel" style="margin-bottom:12px">
                  {#if filterRowFields.length}
                    <div class="filter-panel-row">
                      {#each filterRowFields as ff}
                        {@render filterGroup(ff)}
                      {/each}
                    </div>
                  {/if}
                  {#each otherFilterFields as ff}
                    {@render filterGroup(ff)}
                  {/each}
                </div>
              {/if}

              <table class="table">
                <thead>
                  <tr>
                    <th class="open-dot-col" aria-label="Open on this board"></th>
                    {#each allItemsColumns as f}
                      <th
                        class="sortable"
                        class:sorted={workspace.sort?.field === f.id}
                        style:width={f.list_width || undefined}
                        onclick={() => clickListSort(f.id)}
                      >{f.list_label || f.label}{listSortMark(f.id)}</th>
                    {/each}
                    {#if listHasWaiting}
                      <th
                        class="sortable"
                        class:sorted={workspace.sort?.field === '_waiting'}
                        onclick={() => clickListSort('_waiting')}
                      >Waiting{listSortMark('_waiting')}</th>
                    {/if}
                    <th
                      class="sortable"
                      class:sorted={workspace.sort?.field === '_updated'}
                      onclick={() => clickListSort('_updated')}
                    >Updated{listSortMark('_updated')}</th>
                  </tr>
                </thead>
                <tbody>
                  {#each filteredItems as it}
                    <tr
                      class="clickable"
                      ondblclick={(e) => onAllItemsRowDblClick(e, it.id)}
                      oncontextmenu={(e) => openItemContextMenu(e, it)}
                    >
                      <td class="open-dot-col">
                        <span
                          class="open-dot"
                          class:lit={openItemIds.has(it.id)}
                          title={openItemIds.has(it.id) ? 'Open on this board' : 'Not open on this board'}
                          aria-hidden="true"
                        ></span>
                      </td>
                      {#each allItemsColumns as f}
                        <td>{f.id === 'waiting_for' && !isItemWaiting(it) ? '' : String(it.fields[f.id] ?? '')}</td>
                      {/each}
                      {#if listHasWaiting}
                        <td>
                          {#if isItemWaiting(it)}
                            <span class="waiting-badge">
                              {formatWaitingDays(
                                liveSeconds(it.waiting.current_started_at, nowTick) ??
                                  it.waiting.current_seconds
                              )}
                            </span>
                          {/if}
                        </td>
                      {/if}
                      <td class="updated-date">{formatItemUpdatedDate(it.updated_at)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
              {#if !filteredItems.length}
                <div class="empty-hint">No items match filters. Create one or clear filters.</div>
              {/if}
            {:else if panel.kind === 'notes'}
              {#key `${project.slug}:${workspace.id}`}
                <div class="field-row field-row-fill">
                  <RichText fill value={notesContent} onchange={(json) => void saveNotes(json)} />
                </div>
              {/key}
            {:else if panel.kind === 'deliverables'}
              <div class="toolbar-row">
                <button type="button" class="primary" onclick={addDeliverable}>Add</button>
              </div>
              {#each deliverables as d, i}
                <div class="toolbar-row" style="align-items:flex-start">
                  <input
                    type="checkbox"
                    style="width:auto;margin-top:8px"
                    checked={Boolean(d.done)}
                    onchange={(e) => {
                      const next = deliverables.map((x, j) =>
                        j === i ? { ...x, done: e.currentTarget.checked } : x
                      );
                      void saveDeliverables(next);
                    }}
                  />
                  <input
                    type="text"
                    placeholder="Deliverable title"
                    value={String(d.title ?? '')}
                    oninput={(e) => {
                      const next = deliverables.map((x, j) =>
                        j === i ? { ...x, title: e.currentTarget.value } : x
                      );
                      deliverables = next;
                    }}
                    onchange={() => void saveDeliverables(deliverables)}
                  />
                  <button
                    type="button"
                    class="ghost"
                    onclick={() => void saveDeliverables(deliverables.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                </div>
              {/each}
            {/if}
          </FloatingPanel>
        {/each}
      </div>
    </div>
  </div>
{/if}

{#if toast}
  <div class="toast">{toast}</div>
{/if}
