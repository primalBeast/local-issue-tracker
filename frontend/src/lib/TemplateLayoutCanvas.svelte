<script lang="ts">
  import type { FieldDef } from './api';
  import { lineVisibilityHint } from './templateLabels';
  import {
    displayRowNumber,
    displayWidth,
    dropOnLine,
    dropOnNewRow,
    groupFieldsByLine,
    resizeFromEdge,
    widthFromEdgePointer,
  } from './templatePlacement';

  interface Props {
    fields: FieldDef[];
    selectedId: string | null;
    disabled: boolean;
    onfields: (next: FieldDef[]) => void;
    onselect: (id: string) => void;
    onadd: () => void;
  }

  let { fields, selectedId, disabled, onfields, onselect, onadd }: Props = $props();

  let groups = $derived(groupFieldsByLine(fields));

  type DragState = {
    id: string;
    x: number;
    y: number;
    label: string;
    over: { kind: 'line'; line: number; slot: number } | { kind: 'new'; after: number | null } | null;
  };

  let drag = $state<DragState | null>(null);
  let resizing = $state<{ leftId: string; rowLeft: number; rowWidth: number } | null>(null);

  function slotFromPoint(rowEl: HTMLElement, clientX: number, draggedId: string): number {
    const chips = [...rowEl.querySelectorAll<HTMLElement>('[data-field-id]')].filter(
      (el) => el.dataset.fieldId !== draggedId
    );
    let slot = 1;
    for (const chip of chips) {
      const r = chip.getBoundingClientRect();
      if (clientX > (r.left + r.right) / 2) slot += 1;
      else break;
    }
    return slot;
  }

  function targetFromPoint(clientX: number, clientY: number, draggedId: string): DragState['over'] {
    const hit = document.elementFromPoint(clientX, clientY) as HTMLElement | null;
    const gap = hit?.closest?.('[data-drop-new]') as HTMLElement | null;
    if (gap) {
      const raw = gap.dataset.dropNew;
      return { kind: 'new', after: raw === '' || raw == null ? null : Number(raw) };
    }
    const row = hit?.closest?.('[data-drop-line]') as HTMLElement | null;
    if (row) {
      const line = Number(row.dataset.dropLine);
      return { kind: 'line', line, slot: slotFromPoint(row, clientX, draggedId) };
    }
    return null;
  }

  function onChipPointerDown(e: PointerEvent, f: FieldDef) {
    if (disabled || e.button !== 0) return;
    if ((e.target as HTMLElement | null)?.closest?.('.template-resize')) return;
    onselect(f.id);
    const startX = e.clientX;
    const startY = e.clientY;
    const pointerId = e.pointerId;
    const target = e.currentTarget as HTMLElement;
    let started = false;
    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return;
      if (!started) {
        if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < 4) return;
        started = true;
        target.setPointerCapture(pointerId);
        drag = { id: f.id, x: ev.clientX, y: ev.clientY, label: f.label, over: null };
      }
      if (!drag) return;
      drag = {
        ...drag,
        x: ev.clientX,
        y: ev.clientY,
        over: targetFromPoint(ev.clientX, ev.clientY, f.id),
      };
    };
    const onUp = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      if (started) {
        try {
          target.releasePointerCapture(pointerId);
        } catch {
          /* already released */
        }
        const over = drag?.over ?? targetFromPoint(ev.clientX, ev.clientY, f.id);
        drag = null;
        if (over?.kind === 'line') onfields(dropOnLine(fields, f.id, over.line, over.slot));
        else if (over?.kind === 'new') onfields(dropOnNewRow(fields, f.id, over.after));
      } else {
        drag = null;
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  }

  function onResizePointerDown(e: PointerEvent, left: FieldDef, rowEl: HTMLElement) {
    if (disabled || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const rect = rowEl.getBoundingClientRect();
    const pointerId = e.pointerId;
    (e.currentTarget as HTMLElement).setPointerCapture(pointerId);
    resizing = { leftId: left.id, rowLeft: rect.left, rowWidth: rect.width };
    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId || !resizing) return;
      onfields(resizeFromEdge(fields, resizing.leftId, widthFromEdgePointer(resizing.rowLeft, resizing.rowWidth, ev.clientX)));
    };
    const onUp = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId) return;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      resizing = null;
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  }
</script>

<div class="template-canvas">
  <div class="template-canvas-head">
    <div class="template-preview-label">Layout</div>
    <button type="button" class="ghost" disabled={disabled} onclick={onadd}>Add field</button>
  </div>
  <div class="template-canvas-rows" class:is-dragging={Boolean(drag)}>
    <div
      class="template-newrow-gap"
      class:active={drag?.over?.kind === 'new' && drag.over.after == null}
      data-drop-new=""
    >
      {#if drag}Drop here for a new row{/if}
    </div>
    {#each groups as group (group.line)}
      {@const when = lineVisibilityHint(group.fields, fields)}
      {@const rowNo = displayRowNumber(fields, group.line)}
      <section
        class="template-line"
        class:drop-target={drag?.over?.kind === 'line' && drag.over.line === group.line}
        data-drop-line={group.line}
      >
        <div class="template-line-head">
          Row {rowNo}
          <span class="template-line-count"
            >{group.fields.length === 1 ? '1 field' : `${group.fields.length} fields`}</span
          >
          {#if when}
            <span class="template-line-when">{when}</span>
          {/if}
        </div>
        <div class="template-line-chips">
          {#each group.fields as f, fi (f.id)}
            {#if fi > 0 && group.fields[fi - 1]}
              {@const prev = group.fields[fi - 1]}
              <button
                type="button"
                class="template-resize"
                tabindex={disabled ? -1 : 0}
                disabled={disabled}
                aria-label="Resize {prev.label} and {f.label}"
                onpointerdown={(e) =>
                  onResizePointerDown(e, prev, (e.currentTarget as HTMLElement).closest('.template-line-chips')!)}
              ></button>
            {/if}
            <button
              type="button"
              class="template-chip"
              class:selected={selectedId === f.id}
              class:dragging={drag?.id === f.id}
              data-field-id={f.id}
              style:flex={`${displayWidth(f, fields)} 1 0`}
              onpointerdown={(e) => onChipPointerDown(e, f)}
              onclick={() => onselect(f.id)}
            >
              <span class="template-chip-label">{f.label}</span>
            </button>
          {/each}
        </div>
      </section>
      <div
        class="template-newrow-gap"
        class:active={drag?.over?.kind === 'new' && drag.over.after === group.line}
        data-drop-new={group.line}
      >
        {#if drag}Drop here for a new row{/if}
      </div>
    {/each}
  </div>
</div>

{#if drag}
  <div class="template-drag-ghost" style:left="{drag.x + 8}px" style:top="{drag.y + 8}px">{drag.label}</div>
{/if}
