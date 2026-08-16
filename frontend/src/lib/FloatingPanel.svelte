<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { Panel } from './api';
  import { MIN_PANEL_H, MIN_PANEL_W, snapSize, snapToGrid } from './snap';

  interface Props {
    panel: Panel;
    zoom: number;
    active?: boolean;
    title: string;
    accentBorder?: string;
    accentBg?: string;
    compact?: boolean;
    onfocus: () => void;
    onmove: (patch: Partial<Panel>) => void;
    onclose: () => void;
    children?: import('svelte').Snippet;
    compactChildren?: import('svelte').Snippet;
  }

  let {
    panel,
    zoom,
    active = false,
    title,
    accentBorder,
    accentBg,
    compact = false,
    onfocus,
    onmove,
    onclose,
    children,
    compactChildren,
  }: Props = $props();

  const gesture = {
    mode: null as null | 'drag' | 'resize',
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
      const size = snapSize(gesture.origW + dx, gesture.origH + dy, z);
      onmove({
        width: Math.max(MIN_PANEL_W, size.width),
        height: Math.max(MIN_PANEL_H, size.height),
      });
    }
  }

  function onWindowPointerUp(e: PointerEvent) {
    if (gesture.mode === null) return;
    if (gesture.pointerId >= 0 && e.pointerId !== gesture.pointerId) return;
    endGesture();
  }

  function beginGesture(e: PointerEvent, mode: 'drag' | 'resize') {
    if (e.button !== undefined && e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();

    gesture.mode = mode;
    gesture.pointerId = e.pointerId ?? -1;
    gesture.startX = e.clientX;
    gesture.startY = e.clientY;
    gesture.origX = panel.x;
    gesture.origY = panel.y;
    gesture.origW = panel.width;
    gesture.origH = panel.height;
    gesture.zoom = zoom || 1;

    document.body.classList.add('lit-panel-dragging');
    onfocus();

    cleanup();
    window.addEventListener('pointermove', onWindowPointerMove, true);
    window.addEventListener('pointerup', onWindowPointerUp, true);
    window.addEventListener('pointercancel', onWindowPointerUp, true);
  }

  function onHeaderPointerDown(e: PointerEvent) {
    const t = e.target as HTMLElement | null;
    if (t?.closest?.('button')) return;
    beginGesture(e, 'drag');
  }

  function onResizeDown(e: PointerEvent) {
    beginGesture(e, 'resize');
  }

  onDestroy(endGesture);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="panel"
  class:active
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
  onpointerdown={() => onfocus()}
>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="panel-header"
    role="toolbar"
    tabindex="-1"
    onpointerdown={onHeaderPointerDown}
  >
    <div class="panel-title">{title}</div>
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
    <div class="panel-body compact">
      {#if compactChildren}
        {@render compactChildren()}
      {:else}
        <div class="compact-id">{title}</div>
      {/if}
    </div>
  {:else}
    <div class="panel-body">
      {#if children}
        {@render children()}
      {/if}
    </div>
  {/if}

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="resize-handle"
    role="separator"
    aria-orientation="horizontal"
    title="Drag to resize"
    onpointerdown={onResizeDown}
  ></div>
</div>
