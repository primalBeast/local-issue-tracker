<script lang="ts">
  import { tick, untrack } from 'svelte';
  import type { FieldDef } from './api';
  import { calendarMonth, monthLabel, parseIsoDate } from './listCalendar';
  import { todayLocalDate, waitingNameChoices } from './waiting';

  interface Props {
    def: FieldDef;
    value: unknown;
    display: string;
    editing: boolean;
    onCommit: (value: unknown) => void;
    onEnd: () => void;
  }

  let { def, value, display, editing, onCommit, onEnd }: Props = $props();

  function selectOptions(): string[] {
    return waitingNameChoices(def.options, value);
  }

  let selectSize = $derived(
    Math.max(1, selectOptions().length + (def.required ? 0 : 1))
  );

  let selectBoxEl = $state<HTMLDivElement | undefined>(undefined);
  let selectAnchorEl = $state<HTMLElement | undefined>(undefined);
  let inputEl = $state<HTMLInputElement | undefined>(undefined);
  let selectPopup = $state({ top: 0, left: 0, width: 160, maxHeight: 240, ready: false });
  let datePopup = $state({ top: 0, left: 0, ready: false });
  let viewYear = $state(0);
  let viewMonth = $state(0);
  let draft = $state('');
  let original: unknown = undefined;
  let flushed = false;
  let placingCaret = false;
  const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const dateCells = $derived(calendarMonth(viewYear, viewMonth));
  const todayIso = todayLocalDate();
  const selectedIso = $derived(String(draft || original || ''));

  function portalToBody(node: HTMLElement) {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  }

  function positionSelectPopup() {
    const cell = selectAnchorEl?.closest('td') ?? selectAnchorEl;
    if (!cell) return;
    const r = cell.getBoundingClientRect();
    const wanted = Math.min(280, selectSize * 22 + 10);
    const gap = 4;
    const spaceBelow = window.innerHeight - r.bottom - gap;
    const spaceAbove = r.top - gap;
    let maxHeight = wanted;
    let top = r.bottom + gap;
    if (spaceBelow < 96 && spaceAbove > spaceBelow) {
      maxHeight = Math.max(72, Math.min(wanted, spaceAbove));
      top = r.top - maxHeight;
    } else {
      maxHeight = Math.max(72, Math.min(wanted, spaceBelow));
    }
    selectPopup = {
      top,
      left: r.left,
      width: Math.max(r.width, 128),
      maxHeight,
      ready: true,
    };
  }

  function positionDatePopup() {
    const cell = selectAnchorEl?.closest('td') ?? selectAnchorEl;
    if (!cell) return;
    const r = cell.getBoundingClientRect();
    const width = 252;
    const height = def.required ? 268 : 300;
    const gap = 4;
    const spaceBelow = window.innerHeight - r.bottom - gap;
    const spaceAbove = r.top - gap;
    let top = r.bottom + gap;
    if (spaceBelow < height && spaceAbove > spaceBelow) {
      top = Math.max(8, r.top - height);
    } else if (top + height > window.innerHeight - 8) {
      top = Math.max(8, window.innerHeight - height - 8);
    }
    let left = r.left;
    if (left + width > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - width - 8);
    }
    datePopup = { top, left, ready: true };
  }

  function placeCaretAtEnd(el: HTMLInputElement) {
    placingCaret = true;
    el.focus();
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    const len = el.value.length;
    try {
      el.setSelectionRange(len, len);
    } catch {
      if (el.type === 'number') {
        el.type = 'text';
        el.setSelectionRange(len, len);
        el.type = 'number';
      }
    }
    placingCaret = false;
  }

  function draftFromValue(v: unknown): string {
    if (v == null || v === '') return '';
    return String(v);
  }

  function sameValue(a: unknown, b: unknown): boolean {
    if (a === b) return true;
    if ((a == null || a === '') && (b == null || b === '')) return true;
    if (def.type === 'number') {
      if (a == null || a === '' || b == null || b === '') return false;
      return Number(a) === Number(b);
    }
    return String(a ?? '') === String(b ?? '');
  }

  function parsedDraft(): { ok: boolean; value: unknown } {
    const raw = draft;
    if (def.type === 'number') {
      if (raw.trim() === '') {
        return def.required ? { ok: false, value: null } : { ok: true, value: null };
      }
      const n = Number(raw);
      if (!Number.isFinite(n)) return { ok: false, value: null };
      const min = def.validation?.min;
      const max = def.validation?.max;
      if (typeof min === 'number' && n < min) return { ok: false, value: n };
      if (typeof max === 'number' && n > max) return { ok: false, value: n };
      return { ok: true, value: n };
    }
    if (def.required && raw.trim() === '') return { ok: false, value: raw };
    return { ok: true, value: raw };
  }

  function flush() {
    if (flushed) return;
    flushed = true;
    const parsed = parsedDraft();
    if (!parsed.ok) return;
    if (sameValue(parsed.value, original)) return;
    onCommit(parsed.value);
  }

  function finish() {
    if (placingCaret) return;
    flush();
    onEnd();
  }

  $effect(() => {
    if (!editing) return;
    if (def.type === 'select' || def.type === 'checkbox') return;
    flushed = false;
    original = untrack(() => value);
    draft = draftFromValue(original);
    if (def.type === 'date') {
      const d = parseIsoDate(original) ?? new Date();
      viewYear = d.getFullYear();
      viewMonth = d.getMonth();
      return () => {
        flush();
      };
    }
    void tick().then(() => {
      if (!editing || !inputEl) return;
      placeCaretAtEnd(inputEl);
    });
    return () => {
      flush();
    };
  });

  $effect(() => {
    if (!editing || (def.type !== 'select' && def.type !== 'date')) return;
    const sync = () => {
      if (def.type === 'date') positionDatePopup();
      else positionSelectPopup();
      selectBoxEl?.focus();
    };
    void tick().then(sync);
    window.addEventListener('scroll', sync, true);
    window.addEventListener('resize', sync);
    return () => {
      window.removeEventListener('scroll', sync, true);
      window.removeEventListener('resize', sync);
    };
  });

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Tab') {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (e.key !== 'Enter' && e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as HTMLElement).blur();
  }

  function pickSelect(opt: string) {
    onCommit(opt);
    onEnd();
  }

  function pickDate(iso: string) {
    flushed = true;
    if (!sameValue(iso, original)) onCommit(iso);
    onEnd();
  }

  function shiftMonth(delta: number) {
    const d = new Date(viewYear, viewMonth + delta, 1);
    viewYear = d.getFullYear();
    viewMonth = d.getMonth();
  }
</script>

{#if editing}
  {#if def.type === 'select'}
    <span class="list-cell-edit list-select-anchor" bind:this={selectAnchorEl}>{display || '\u00a0'}</span>
    <div
      class="list-select-popup"
      role="listbox"
      tabindex="0"
      use:portalToBody
      bind:this={selectBoxEl}
      style:top="{selectPopup.top}px"
      style:left="{selectPopup.left}px"
      style:width="{selectPopup.width}px"
      style:max-height="{selectPopup.maxHeight}px"
      style:visibility={selectPopup.ready ? 'visible' : 'hidden'}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onblur={onEnd}
      onkeydown={onKey}
    >
      {#if !def.required}
        <button
          type="button"
          class="list-select-opt"
          class:selected={value == null || value === ''}
          role="option"
          aria-label="Clear"
          aria-selected={value == null || value === ''}
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => pickSelect('')}
        ></button>
      {/if}
      {#each selectOptions() as opt}
        <button
          type="button"
          class="list-select-opt"
          class:selected={String(value ?? '') === opt}
          role="option"
          aria-selected={String(value ?? '') === opt}
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => pickSelect(opt)}
        >{opt}</button>
      {/each}
    </div>
  {:else if def.type === 'number'}
    <input
      class="list-cell-edit"
      type="number"
      min={def.validation?.min as number | undefined}
      max={def.validation?.max as number | undefined}
      step={(def.validation?.step as number | undefined) ?? 1}
      bind:this={inputEl}
      value={draft}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => {
        draft = e.currentTarget.value;
      }}
      onblur={finish}
      onkeydown={onKey}
    />
  {:else if def.type === 'checkbox'}
    <input
      class="list-cell-edit"
      type="checkbox"
      checked={Boolean(value)}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onchange={(e) => {
        onCommit(e.currentTarget.checked);
        onEnd();
      }}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {:else if def.type === 'date'}
    <span class="list-cell-edit list-select-anchor" bind:this={selectAnchorEl}>{display || '\u00a0'}</span>
    <div
      class="list-date-popup"
      role="dialog"
      aria-label="Choose date"
      tabindex="0"
      use:portalToBody
      bind:this={selectBoxEl}
      style:top="{datePopup.top}px"
      style:left="{datePopup.left}px"
      style:visibility={datePopup.ready ? 'visible' : 'hidden'}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onblur={onEnd}
      onkeydown={onKey}
    >
      <div class="list-date-head">
        <button
          type="button"
          aria-label="Previous month"
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => shiftMonth(-1)}
        >‹</button>
        <div class="list-date-title">{monthLabel(viewYear, viewMonth)}</div>
        <button
          type="button"
          aria-label="Next month"
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => shiftMonth(1)}
        >›</button>
      </div>
      <div class="list-date-weekdays">
        {#each WEEKDAYS as w, i (i)}
          <span>{w}</span>
        {/each}
      </div>
      <div class="list-date-grid">
        {#each dateCells as cell (cell.iso)}
          <button
            type="button"
            class="list-date-day"
            class:muted={!cell.inMonth}
            class:selected={cell.iso === selectedIso}
            class:today={cell.iso === todayIso}
            onpointerdown={(e) => e.preventDefault()}
            onclick={() => pickDate(cell.iso)}
          >{cell.day}</button>
        {/each}
      </div>
      {#if !def.required}
        <button
          type="button"
          class="list-date-clear"
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => pickDate('')}
        >Clear</button>
      {/if}
    </div>
  {:else if def.type === 'datetime'}
    <input
      class="list-cell-edit"
      type="datetime-local"
      bind:this={inputEl}
      value={draft}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => {
        draft = e.currentTarget.value;
      }}
      onblur={finish}
      onkeydown={onKey}
    />
  {:else}
    <input
      class="list-cell-edit"
      type="text"
      bind:this={inputEl}
      value={draft}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => {
        draft = e.currentTarget.value;
      }}
      onblur={finish}
      onkeydown={onKey}
    />
  {/if}
{:else}
  <span class="list-cell-label">{display}</span>
{/if}
