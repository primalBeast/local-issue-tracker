<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { Panel } from './api';
  import { resizeCursor, resizeFromEdge, snapToGrid, type ResizeEdge } from './snap';

  interface Props {
    panel: Panel;
    zoom: number;
    active?: boolean;
    title: string;
    accentBorder?: string;
    accentBg?: string;
    compact?: boolean;
    /** Stretch children so a trailing Notes field can fill leftover height. */
    fillBody?: boolean;
    onfocus: () => void;
    onmove: (patch: Partial<Panel>) => void;
    onclose: () => void;
    oncontext?: (e: MouseEvent) => void;
    children?: import('svelte').Snippet;
    compactChildren?: import('svelte').Snippet;
    /** Replaces the plain title text (e.g. ticket number + description editor). */
    titleSlot?: import('svelte').Snippet;
  }

  let {
    panel,
    zoom,
    active = false,
    title,
    accentBorder,
    accentBg,
    compact = false,
    fillBody = false,
    onfocus,
    onmove,
    onclose,
    oncontext,
    children,
    compactChildren,
    titleSlot,
  }: Props = $props();

  const gesture = {
    mode: null as null | 'drag' | 'resize',
    edge: 'se' as ResizeEdge,
    startX: 0,
    startY: 0,
    origX: 0,
    origY: 0,
    origW: 0,
    origH: 0,
    zoom: 1,
    pointerId: -1,
  };

  function cleanup() {
    window.removeEventListener('pointermove', onWindowPointerMove, true);
    window.removeEventListener('pointerup', onWindowPointerUp, true);
    window.removeEventListener('pointercancel', onWindowPointerUp, true);
    document.body.classList.remove('lit-panel-dragging');
    document.body.classList.remove('lit-panel-resizing');
    document.body.style.cursor = '';
  }

  function endGesture() {
    gesture.mode = null;
    gesture.pointerId = -1;
    cleanup();
  }

  function onWindowPointerMove(e: PointerEvent) {
    if (gesture.mode === null) return;
    if (gesture.pointerId >= 0 && e.pointerId !== gesture.pointerId) return;
    e.preventDefault();
    const z = gesture.zoom || 1;
    const dx = (e.clientX - gesture.startX) / z;
    const dy = (e.clientY - gesture.startY) / z;
    if (gesture.mode === 'drag') {
      onmove({
        x: snapToGrid(gesture.origX + dx, z),
        y: snapToGrid(gesture.origY + dy, z),
      });
    } else {
      onmove(
        resizeFromEdge(
          {
            x: gesture.origX,
            y: gesture.origY,
            width: gesture.origW,
            height: gesture.origH,
          },
          gesture.edge,
          dx,
          dy,
          z
        )
      );
    }
  }

  function onWindowPointerUp(e: PointerEvent) {
    if (gesture.mode === null) return;
    if (gesture.pointerId >= 0 && e.pointerId !== gesture.pointerId) return;
    endGesture();
  }

  function beginGesture(e: PointerEvent, mode: 'drag' | 'resize', edge: ResizeEdge = 'se') {
    if (e.button !== undefined && e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();

    gesture.mode = mode;
    gesture.edge = edge;
    gesture.pointerId = e.pointerId ?? -1;
    gesture.startX = e.clientX;
    gesture.startY = e.clientY;
    gesture.origX = panel.x;
    gesture.origY = panel.y;
    gesture.origW = panel.width;
    gesture.origH = panel.height;
    gesture.zoom = zoom || 1;

    if (mode === 'drag') {
      document.body.classList.add('lit-panel-dragging');
    } else {
      document.body.classList.add('lit-panel-resizing');
      document.body.style.cursor = resizeCursor(edge);
    }
    onfocus();

    cleanup();
    window.addEventListener('pointermove', onWindowPointerMove, true);
    window.addEventListener('pointerup', onWindowPointerUp, true);
    window.addEventListener('pointercancel', onWindowPointerUp, true);
  }

  function onHeaderPointerDown(e: PointerEvent) {
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('button, input, textarea, select, .item-title-editor')) return;
    beginGesture(e, 'drag');
  }

  function onCompactPointerDown(e: PointerEvent) {
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('button')) return;
    beginGesture(e, 'drag');
  }

  function onResizeDown(e: PointerEvent, edge: ResizeEdge) {
    beginGesture(e, 'resize', edge);
  }

  onDestroy(endGesture);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="panel"
  class:active
  class:panel-compact={compact}
  role="dialog"
  tabindex="-1"
  aria-label={title}
  style:left="{panel.x}px"
  style:top="{panel.y}px"
  style:width="{panel.width}px"
  style:height="{panel.height}px"
  style:z-index={panel.z_index}
  style:background={accentBg || undefined}
  style:border-color={accentBorder || undefined}
  onpointerdown={(e) => {
    e.stopPropagation();
    onfocus();
  }}
  oncontextmenu={(e) => {
    if (!oncontext) return;
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('input, textarea, select, button, .ProseMirror, .item-title-editor')) return;
    e.preventDefault();
    e.stopPropagation();
    oncontext(e);
  }}
>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="panel-header"
    role="toolbar"
    tabindex="-1"
    onpointerdown={onHeaderPointerDown}
  >
    {#if titleSlot}
      <div class="panel-title-slot">{@render titleSlot()}</div>
    {:else}
      <div class="panel-title">{title}</div>
    {/if}
    <button
      class="ghost"
      type="button"
      title="Close"
      onclick={(e) => {
        e.stopPropagation();
        onclose();
      }}
      >✕</button
    >
  </div>

  {#if compact}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="panel-body compact" onpointerdown={onCompactPointerDown}>
      {#if compactChildren}
        {@render compactChildren()}
      {:else}
        <div class="compact-id">{title}</div>
      {/if}
    </div>
  {:else}
    <div class="panel-body" class:panel-body-fill={fillBody}>
      {#if children}
        {@render children()}
      {/if}
    </div>
  {/if}

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-edge resize-n" role="separator" aria-orientation="horizontal" title="Resize" onpointerdown={(e) => onResizeDown(e, 'n')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-edge resize-s" role="separator" aria-orientation="horizontal" title="Resize" onpointerdown={(e) => onResizeDown(e, 's')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-edge resize-e" role="separator" aria-orientation="vertical" title="Resize" onpointerdown={(e) => onResizeDown(e, 'e')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-edge resize-w" role="separator" aria-orientation="vertical" title="Resize" onpointerdown={(e) => onResizeDown(e, 'w')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-corner resize-nw" role="separator" title="Resize" onpointerdown={(e) => onResizeDown(e, 'nw')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-corner resize-ne" role="separator" title="Resize" onpointerdown={(e) => onResizeDown(e, 'ne')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-corner resize-sw" role="separator" title="Resize" onpointerdown={(e) => onResizeDown(e, 'sw')}></div>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="resize-corner resize-se" role="separator" title="Resize" onpointerdown={(e) => onResizeDown(e, 'se')}></div>
</div>
