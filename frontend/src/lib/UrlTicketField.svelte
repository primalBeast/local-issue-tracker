<script lang="ts">
  import { tick } from 'svelte';
  import { launchableHref } from './ticketUrl';
  import { urlTail } from './urlTicket';

  interface Props {
    id: string;
    label: string;
    value: string;
    placeholder?: string;
    showAdd?: boolean;
    onchange: (value: string) => void;
    onAdd?: () => void;
  }

  let {
    id,
    label,
    value,
    placeholder = 'Full URL',
    showAdd = false,
    onchange,
    onAdd,
  }: Props = $props();

  let editing = $state(!String(value ?? '').trim());
  let inputEl = $state<HTMLInputElement | null>(null);
  let clickTimer = 0;

  let compact = $derived(!!String(value ?? '').trim() && !editing);

  $effect(() => {
    if (!String(value ?? '').trim() && !editing) editing = true;
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
    if (String(value ?? '').trim()) editing = false;
  }

  function onInputKeydown(e: KeyboardEvent) {
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
</script>

<div class="field-group url-ticket">
  <label class="field-label" for={id}>{label}</label>
  <div class="url-ticket-control">
    {#if compact}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="url-ticket-tail"
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
