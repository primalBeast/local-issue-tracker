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
  import { itemMatchesFilters, sortItems } from './lib/filters';
  import FieldRenderer from './lib/FieldRenderer.svelte';
  import FloatingPanel from './lib/FloatingPanel.svelte';
  import RichText from './lib/RichText.svelte';
  import { fieldFlex, groupFieldsByRow } from './lib/fieldLayout';
  import { isNotesFillRow, minItemPanelHeight } from './lib/panelSize';
  import { clampZoom, snapToGrid } from './lib/snap';
  import {
    defaultPan,
    fitView,
    panAfterZoom,
    panelsWorldBounds,
    screenToWorld,
    zoomFromWheelDelta,
  } from './lib/viewport';
  import { formatDuration, liveSeconds } from './lib/waiting';

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
  /** Pointer-based tab reorder. Selection is via click (never gated on drag). */
  let dragWsId = $state<string | null>(null);
  let dragOverWsId = $state<string | null>(null);
  const tabDrag = {
    id: null as string | null,
    startX: 0,
    startY: 0,
    dragging: false,
    /** When true, the next click is from a completed drag — ignore it. */
    suppressClick: false,
    pointerId: -1,
  };
  /** Board rename / tab color editor (right-click a tab). */
  let boardEditor = $state<{
    id: string;
    name: string;
    tab_color: string | null;
    x: number;
    y: number;
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
  let fieldRows = $derived(groupFieldsByRow(fieldDefs));
  let listFields = $derived(
    [...fieldDefs]
      .filter((f) => f.show_in_list)
      .sort((a, b) => String(a.order).localeCompare(String(b.order), undefined, { numeric: true }))
  );
  let filterableFields = $derived(fieldDefs.filter((f) => f.filterable));
  let zoom = $derived(workspace?.ui.zoom ?? 1);
  let pan = $derived(workspace?.ui.viewport_scroll ?? defaultPan());
  let compact = $derived(
    !!project && zoom < (project.compact_mode_zoom_threshold ?? 0.55)
  );
  let sidebarVisible = $derived(workspace?.ui.sidebar_visible ?? true);
  let panning = $state(false);
  let canvasWrapEl = $state<HTMLElement | null>(null);
  const canvasPan = {
    pointerId: -1,
    startX: 0,
    startY: 0,
    origX: 0,
    origY: 0,
  };

  /** Main Board (seed id) is always pinned to the top of the tab list. */
  function isMainBoard(w: Workspace): boolean {
    return w.id === 'ws-main';
  }

  function sortWorkspaces(list: Workspace[]): Workspace[] {
    const main = list.filter(isMainBoard);
    const rest = list
      .filter((w) => !isMainBoard(w))
      .sort(
        (a, b) =>
          (a.order ?? 0) - (b.order ?? 0) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id)
      );
    // Main boards first (stable by name/id), then the rest by order
    main.sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    return [...main, ...rest];
  }

  let filteredItems = $derived(
    workspace
      ? sortItems(
          items.filter((it) => itemMatchesFilters(it, workspace!.filters.active, fieldDefs)),
          workspace.sort
        )
      : items
  );

  onMount(() => {
    const tick = setInterval(() => (nowTick = Date.now()), 1000);
    void bootstrap();
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        toggleSidebar();
      }
      if (e.key === 'Escape') boardEditor = null;
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
      if (!boardEditor) return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.('.board-editor')) return;
      if (t?.closest?.('.ws-tab')) return; // tab open/context menu owns the click
      boardEditor = null;
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onDocPointerDown, true);
    return () => {
      clearInterval(tick);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onDocPointerDown, true);
      endCanvasPan();
    };
  });

  async function bootstrap() {
    try {
      loading = true;
      projects = await api.projects();
      if (!projects.length) {
        error = 'No projects found. Run lit serve to auto-seed, or lit init-project.';
        return;
      }
      const settings = await api.settings();
      const slug =
        (settings.last_project_slug as string) || projects[0].slug;
      await loadProject(slug);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
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

    // Do not overwrite last_workspace when only updating last_project_slug
    try {
      await api.patchSettings({ last_project_slug: slug });
    } catch (e) {
      console.error(e);
    }

    if (workspace) {
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
    void rememberLastWorkspace(id);

    // Refresh from server in the background (do not block UI)
    try {
      const fresh = await api.workspace(project.slug, id);
      if (workspace?.id !== id) return; // user already switched again
      workspace = fresh;
      workspaces = sortWorkspaces(workspaces.map((w) => (w.id === id ? fresh : w)));
      for (const p of fresh.panels || []) {
        if (p.kind === 'item' && p.item_id) await ensureDetail(p.item_id);
      }
    } catch (e) {
      // Keep local board; do not stick the user on a failed network call
      console.error(e);
    }
  }

  async function persistWorkspaceOrders(list: Workspace[]) {
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
      showToast('Failed to save board order');
      console.error(e);
    }
  }

  function reorderWorkspaceBefore(fromId: string, overId: string) {
    if (fromId === overId) return;
    const from = workspaces.find((w) => w.id === fromId);
    const over = workspaces.find((w) => w.id === overId);
    if (!from || !over || isMainBoard(from) || isMainBoard(over)) return;

    const main = workspaces.filter(isMainBoard).map(cloneWorkspace);
    let rest = workspaces.filter((w) => !isMainBoard(w)).map(cloneWorkspace);
    const fromIdx = rest.findIndex((w) => w.id === fromId);
    const toIdx = rest.findIndex((w) => w.id === overId);
    if (fromIdx < 0 || toIdx < 0) return;
    const [moved] = rest.splice(fromIdx, 1);
    rest.splice(toIdx, 0, moved);

    for (const m of main) m.order = 0;
    rest = rest.map((w, i) => ({ ...w, order: i + 1 }));
    const next = sortWorkspaces([...main, ...rest]);
    workspaces = next;
    void persistWorkspaceOrders(next);
  }

  function clearTabWindowListeners() {
    window.removeEventListener('pointermove', onTabWindowMove, true);
    window.removeEventListener('pointerup', onTabWindowUp, true);
    window.removeEventListener('pointercancel', onTabWindowUp, true);
  }

  function resetTabDrag() {
    tabDrag.id = null;
    tabDrag.dragging = false;
    tabDrag.pointerId = -1;
    dragWsId = null;
    dragOverWsId = null;
    clearTabWindowListeners();
  }

  /** Board select — always works via normal click. Drag only reorders. */
  function onTabClick(id: string) {
    void selectWorkspace(id);
  }

  function onTabPointerDown(e: PointerEvent, id: string) {
    if (e.button !== 0) return;
    // Arm a potential reorder only; selection is always via onclick.
    tabDrag.id = id;
    tabDrag.startX = e.clientX;
    tabDrag.startY = e.clientY;
    tabDrag.dragging = false;
    tabDrag.suppressClick = false;
    tabDrag.pointerId = e.pointerId;
    clearTabWindowListeners();
    window.addEventListener('pointermove', onTabWindowMove, true);
    window.addEventListener('pointerup', onTabWindowUp, true);
    window.addEventListener('pointercancel', onTabWindowUp, true);
  }

  function onTabWindowMove(e: PointerEvent) {
    if (tabDrag.pointerId !== e.pointerId || !tabDrag.id) return;
    const w = workspaces.find((x) => x.id === tabDrag.id);
    // Main board is pinned — never reorder
    if (!w || isMainBoard(w)) return;

    const dx = Math.abs(e.clientX - tabDrag.startX);
    const dy = Math.abs(e.clientY - tabDrag.startY);
    if (!tabDrag.dragging && (dx > 12 || dy > 12)) {
      tabDrag.dragging = true;
      dragWsId = tabDrag.id;
    }
    if (!tabDrag.dragging) return;

    const el = document.elementFromPoint(e.clientX, e.clientY);
    const tabEl = el?.closest?.('[data-ws-id]') as HTMLElement | null;
    const overId = tabEl?.dataset?.wsId ?? null;
    if (!overId || overId === tabDrag.id) {
      dragOverWsId = null;
      return;
    }
    const over = workspaces.find((x) => x.id === overId);
    if (!over || isMainBoard(over)) {
      dragOverWsId = null;
      return;
    }
    dragOverWsId = overId;
  }

  function onTabWindowUp(e: PointerEvent) {
    if (tabDrag.pointerId !== e.pointerId) return;
    const wasDrag = tabDrag.dragging;
    const fromId = tabDrag.id;
    const dropId = dragOverWsId;
    resetTabDrag();
    // Reorder only — never suppress the click that selects the board
    if (wasDrag && fromId && dropId) {
      reorderWorkspaceBefore(fromId, dropId);
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

  function onCanvasPointerDown(e: PointerEvent) {
    if (e.button !== 0 || !workspace) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('.panel')) return;
    if (t?.closest?.('.board-editor')) return;
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
    endCanvasPan();
  }

  function visibleWorldOrigin(): { x: number; y: number } {
    return screenToWorld(pan, zoom || 1, { x: 0, y: 0 });
  }

  function maxZ(): number {
    if (!workspace?.panels.length) return 1;
    return Math.max(...workspace.panels.map((p) => p.z_index || 0));
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
    });
  }

  function closePanel(id: string) {
    updateWorkspace((ws) => {
      ws.panels = ws.panels.filter((p) => p.id !== id);
    });
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
    const panelH = Math.max(
      minItemPanelHeight(fieldRows),
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
      });
    });
  }

  async function createItem() {
    if (!project) return;
    try {
      const n = items.length + 1;
      const item = await api.createItem(project.slug, {
        ticket_key: `NEW-${n}`,
        title: '',
        priority: 5,
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

  function scheduleItemPatch(itemId: string, fields: Record<string, unknown>) {
    if (!project) return;
    // Optimistic lean list update
    items = items.map((it) =>
      it.id === itemId ? { ...it, fields: { ...it.fields, ...fields } } : it
    );
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

  function primaryId(item: Item): string {
    const key = project?.primary_identifier_field || 'ticket_key';
    const v = String(item.fields[key] ?? '').trim();
    if (v) return v;
    return 'Untitled';
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

  function setFilterOption(fieldId: string, option: string, checked: boolean) {
    updateWorkspace((ws) => {
      const cur = (ws.filters.active[fieldId] as string[] | undefined) || [];
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
    } catch {
      showToast('Notes save failed');
    }
  }

  async function saveDeliverables(next: Array<Record<string, unknown>>) {
    if (!project) return;
    deliverables = next;
    try {
      await api.putDeliverables(project.slug, next);
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

  function resetLayout() {
    updateWorkspace((ws) => {
      ws.ui.viewport_scroll = defaultPan();
      let x = 40;
      let y = 40;
      for (const p of ws.panels) {
        p.x = x;
        p.y = y;
        x += 40;
        y += 30;
      }
    });
    showToast('Layout reset');
  }

  async function newWorkspace() {
    if (!project) return;
    // Save current board into the list (and debounce server save) before leaving
    flushCurrentWorkspaceToList();
    scheduleWorkspaceSave();
    try {
      const maxOrder = Math.max(
        0,
        ...workspaces.filter((w) => !isMainBoard(w)).map((w) => w.order ?? 0)
      );
      const w = await api.createWorkspace(
        project.slug,
        `Board ${workspaces.filter((x) => !isMainBoard(x)).length + 1}`,
        maxOrder + 1
      );
      workspaces = sortWorkspaces([...workspaces, cloneWorkspace(w)]);
      workspace = cloneWorkspace(w);
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
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"></div>
        Local Issue Tracker
      </div>
      <select
        style="width:auto;min-width:160px"
        value={project.slug}
        onchange={(e) => loadProject(e.currentTarget.value)}
      >
        {#each projects as p}
          <option value={p.slug}>{p.name}</option>
        {/each}
      </select>
      <button type="button" class="ghost" title="Toggle sidebar (⌘\)" onclick={toggleSidebar}>
        {sidebarVisible ? 'Hide tabs' : 'Show tabs'}
      </button>
      <button type="button" class="primary" onclick={createItem}>+ Item</button>
      <button type="button" onclick={() => openSpecial('all_items')}>All Items</button>
      <button type="button" onclick={() => openSpecial('notes')}>Notes</button>
      <button type="button" onclick={() => openSpecial('deliverables')}>Deliverables</button>
      <button type="button" onclick={seeAll} title="Zoom to fit every panel on this board">
        See All
      </button>
      <button type="button" class="ghost" onclick={resetLayout}>Reset layout</button>
      <div class="topbar-spacer"></div>
      <div class="topbar-meta">
        {workspace.name} · zoom {(zoom * 100).toFixed(0)}% · scroll to zoom
        {#if compact}<span class="chip">compact</span>{/if}
        <span class="build-stamp" title="UI build id — if this is missing, hard-refresh">ui:2026-08-16a</span>
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
          class:ws-tab-drag-over={dragOverWsId === w.id && dragWsId !== w.id}
          style={tabStyle(w)}
          onclick={() => onTabClick(w.id)}
          onpointerdown={(e) => onTabPointerDown(e, w.id)}
          ondblclick={(e) => openBoardEditor(e, w)}
          oncontextmenu={(e) => openBoardEditor(e, w)}
          title={
            isMainBoard(w)
              ? `${w.name} — click to open; right-click or double-click to rename / set colour`
              : `${w.name} — click to open; drag to reorder; right-click or double-click to rename / set colour`
          }
        >
          {w.name}
        </button>
      {/each}
      <button type="button" class="ws-tab" onclick={() => void newWorkspace()} title="New workspace">+</button>
    </aside>

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
          <button type="button" class="ghost" onclick={() => (boardEditor = null)}>Cancel</button>
          <button type="button" class="primary" onclick={() => void saveBoardEditor()}>Save</button>
        </div>
      </div>
    {/if}

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="canvas-wrap"
      role="application"
      aria-label="Unlimited workspace. Drag empty space to pan. Scroll or Ctrl+scroll zooms toward the pointer."
      bind:this={canvasWrapEl}
      class:is-panning={panning}
      style:--pan-x="{pan.x}px"
      style:--pan-y="{pan.y}px"
      style:--zoom={zoom}
      onpointerdown={onCanvasPointerDown}
    >
      <div class="canvas-grid" aria-hidden="true"></div>
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
                  ? primaryId(item)
                  : 'Item'
                : panel.kind === 'all_items'
                  ? 'All Items'
                  : panel.kind === 'notes'
                    ? 'Project Notes'
                    : 'Deliverables'
            }
            accentBg={colors.bg || undefined}
            accentBorder={colors.border || undefined}
            compact={compact}
            fillBody={panel.kind === 'item' || panel.kind === 'notes'}
            onfocus={() => focusPanel(panel.id)}
            onmove={(patch) => movePanel(panel.id, patch)}
            onclose={() => closePanel(panel.id)}
          >
            {#snippet compactChildren()}
              <div class="compact-id">{panel.kind === 'item' ? (item ? primaryId(item) : '…') : panel.kind === 'all_items' ? 'All Items' : panel.kind === 'notes' ? 'Notes' : 'Deliverables'}</div>
            {/snippet}

            {#if panel.kind === 'item' && item}
              {#if item.waiting?.is_waiting}
                <div class="waiting-badge" style="margin-bottom:8px">
                  ⏱ Waiting
                  {formatDuration(
                    liveSeconds(item.waiting.current_started_at, nowTick) ??
                      item.waiting.current_seconds
                  )}
                  · total {formatDuration(item.waiting.total_seconds)}
                </div>
              {/if}
              {#if !detailCache[item.id]}
                <div class="empty-hint">Loading item…</div>
              {:else}
                {#key item.id}
                  {#each fieldRows as row (row.row)}
                    <div
                      class="field-row"
                      class:field-row-multi={row.fields.length > 1}
                      class:field-row-fill={isNotesFillRow(row)}
                    >
                      {#each row.fields as def (def.id)}
                        <div class="field-col" style:flex={fieldFlex(def)}>
                          <FieldRenderer
                            {def}
                            fill={isNotesFillRow(row)}
                            fields={detailCache[item.id].fields}
                            onchange={(id, value) => scheduleItemPatch(item.id, { [id]: value })}
                          />
                        </div>
                      {/each}
                    </div>
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
                <div class="filter-panel" style="margin-bottom:12px">
                  {#each filterableFields as ff}
                    <div>
                      <div class="filter-group-title">{ff.label}</div>
                      {#if ff.type === 'select' && ff.options}
                        {#each ff.options as opt}
                          <label class="check-row">
                            <input
                              type="checkbox"
                              checked={((workspace.filters.active[ff.id] as string[]) || []).includes(opt)}
                              onchange={(e) => setFilterOption(ff.id, opt, e.currentTarget.checked)}
                            />
                            {opt}
                          </label>
                        {/each}
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}

              <table class="table">
                <thead>
                  <tr>
                    {#each listFields as f}
                      <th style:width={f.list_width || undefined}>{f.label}</th>
                    {/each}
                    <th>Waiting</th>
                  </tr>
                </thead>
                <tbody>
                  {#each filteredItems as it}
                    <tr class="clickable" onclick={() => openItemPanel(it.id)}>
                      {#each listFields as f}
                        <td>{String(it.fields[f.id] ?? '')}</td>
                      {/each}
                      <td>
                        {#if it.waiting?.is_waiting}
                          <span class="waiting-badge">
                            {formatDuration(
                              liveSeconds(it.waiting.current_started_at, nowTick) ??
                                it.waiting.current_seconds
                            )}
                          </span>
                        {:else}
                          —
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
              {#if !filteredItems.length}
                <div class="empty-hint">No items match filters. Create one or clear filters.</div>
              {/if}
            {:else if panel.kind === 'notes'}
              {#key project.slug}
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
