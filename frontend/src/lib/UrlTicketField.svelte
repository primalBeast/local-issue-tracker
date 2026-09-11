<script lang="ts">
  import { tick } from 'svelte';
  import { launchableHref, openSplitTicketView } from './ticketUrl';
  import { urlTail } from './urlTicket';

  interface Props {
    id: string;
    label: string;
    value: string;
    placeholder?: string;
    showAdd?: boolean;
    onchange: (value: string) => void;
    onAdd?: () => void;
    onRemove?: () => void;
    masterHref?: string | null;
  }

  let {
    id,
    label,
    value,
    placeholder = 'Full URL',
    showAdd = false,
    onchange,
    onAdd,
    onRemove,
    masterHref = null,
  }: Props = $props();

  let editing = $state(!String(value ?? '').trim());
  let inputEl = $state<HTMLInputElement | null>(null);
  let clickTimer = 0;

  let compact = $derived(!!String(value ?? '').trim() && !editing);

  $effect(() => {
    if (!String(value ?? '').trim() && !editing) editing = true;
  });

  function collapseToLabel() {
    if (!String(value ?? '').trim()) return;
    editing = false;
  }

  $effect(() => {
    if (!editing) return;
    function onDocPointerDown(e: PointerEvent) {
      const t = e.target;
      if (t instanceof Node && inputEl?.contains(t)) return;
      requestAnimationFrame(() => collapseToLabel());
    }
    document.addEventListener('pointerdown', onDocPointerDown, true);
    return () => document.removeEventListener('pointerdown', onDocPointerDown, true);
  });

  async function enterEdit() {
    editing = true;
    await tick();
    inputEl?.focus();
    inputEl?.select();
  }

  function launch() {
    const href = launchableHref(value);
    if (!href) return;
    window.open(href, '_blank', 'noopener,noreferrer');
  }

  function onTailClick(e: MouseEvent) {
    if (e.detail > 1) return;
    clickTimer = window.setTimeout(() => void enterEdit(), 220);
  }

  function onTailDblClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (clickTimer) window.clearTimeout(clickTimer);
    launch();
  }

  function onInputDblClick(e: MouseEvent) {
    e.preventDefault();
    launch();
  }

  function onBlur() {
    collapseToLabel();
  }

  function onInputKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      collapseToLabel();
      inputEl?.blur();
      return;
    }
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const next = (e.currentTarget as HTMLInputElement).value;
    onchange(next);
    if (String(next ?? '').trim()) editing = false;
    (e.currentTarget as HTMLInputElement).blur();
  }

  function onAddClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    onAdd?.();
  }

  function stopTailClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (clickTimer) window.clearTimeout(clickTimer);
  }

  function onOpenClick(e: MouseEvent) {
    stopTailClick(e);
    launch();
  }

  function onSplitClick(e: MouseEvent) {
    stopTailClick(e);
    openSplitTicketView(masterHref, value);
  }

  function onRemoveClick(e: MouseEvent) {
    stopTailClick(e);
    onRemove?.();
  }
</script>

<div class="field-group url-ticket">
  <label class="field-label" for={id}>{label}</label>
  <div class="url-ticket-control">
    {#if compact}
      <div class="url-ticket-tail">
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="url-ticket-tail-text"
          role="button"
          tabindex="0"
          title="Click to edit full URL · double-click to open"
          onpointerdown={(e) => e.stopPropagation()}
          onclick={onTailClick}
          ondblclick={onTailDblClick}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              void enterEdit();
            }
          }}
        >
          {urlTail(value)}
        </div>
        <div class="url-ticket-actions">
          <button
            type="button"
            class="url-ticket-icon"
            title="Open in a new tab"
            aria-label="Open in a new tab"
            onpointerdown={(e) => e.stopPropagation()}
            onclick={onOpenClick}
          >
            <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
              <rect x="4" y="1.5" width="8" height="13" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.6" />
            </svg>
          </button>
          <button
            type="button"
            class="url-ticket-icon"
            title="Open split view: master ticket left, this ticket right"
            aria-label="Open split view"
            onpointerdown={(e) => e.stopPropagation()}
            onclick={onSplitClick}
          >
            <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
              <rect x="1.5" y="1.5" width="13" height="13" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.6" />
              <line x1="8" y1="1.5" x2="8" y2="14.5" stroke="currentColor" stroke-width="1.6" />
            </svg>
          </button>
          {#if onRemove}
            <button
              type="button"
              class="url-ticket-remove"
              title="Remove this ticket"
              aria-label="Remove this ticket"
              onpointerdown={(e) => e.stopPropagation()}
              onclick={onRemoveClick}
            >×</button>
          {/if}
        </div>
      </div>
    {:else}
      <input
        {id}
        bind:this={inputEl}
        type="text"
        {placeholder}
        value={value}
        autocomplete="off"
        spellcheck="false"
        onpointerdown={(e) => e.stopPropagation()}
        oninput={(e) => onchange(e.currentTarget.value)}
        onkeydown={onInputKeydown}
        onblur={onBlur}
        ondblclick={onInputDblClick}
      />
    {/if}
    {#if showAdd}
      <button
        type="button"
        class="ghost url-ticket-add"
        title="Add another ticket URL"
        onpointerdown={(e) => e.stopPropagation()}
        onclick={onAddClick}
      >
        +
      </button>
    {/if}
  </div>
</div>
