<script lang="ts">
  interface Props {
    ticketKey: string;
    description: string;
    onTicketKey: (value: string) => void;
    onDescription: (value: string) => void;
  }

  let { ticketKey, description, onTicketKey, onDescription }: Props = $props();

  let descTrimmed = $derived(String(description ?? '').trim());
  let userOpen = $state(false);
  let open = $derived(!descTrimmed || userOpen);

  function keyLabel(): string {
    return String(ticketKey ?? '').trim() || 'Untitled';
  }

  function heading(): string {
    return descTrimmed ? `${keyLabel()}  ${descTrimmed}` : keyLabel();
  }

  function toggle(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!descTrimmed) return;
    userOpen = !userOpen;
  }

  function onDescBlur() {
    if (String(description ?? '').trim()) userOpen = false;
  }
</script>

<div class="item-title-bar">
  <div class="item-title-row">
    <div class="item-title-key">{keyLabel()}</div>
    {#if descTrimmed}
      <div class="item-title-desc" title={descTrimmed}>{descTrimmed}</div>
    {/if}
    <button
      type="button"
      class="ghost item-title-toggle"
      class:open
      title={descTrimmed ? 'Edit ticket number and description' : 'Add a description'}
      aria-expanded={open}
      onclick={toggle}
    >
      ▾
    </button>
  </div>
  {#if open}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="item-title-editor" onpointerdown={(e) => e.stopPropagation()}>
      <label class="item-title-field">
        <span class="field-label">Ticket number</span>
        <input
          type="text"
          value={ticketKey}
          placeholder="PROJ-123"
          autocomplete="off"
          oninput={(e) => onTicketKey(e.currentTarget.value)}
        />
      </label>
      <label class="item-title-field">
        <span class="field-label">Description</span>
        <input
          type="text"
          value={description}
          placeholder="Short description"
          autocomplete="off"
          oninput={(e) => onDescription(e.currentTarget.value)}
          onblur={onDescBlur}
        />
      </label>
    </div>
  {/if}
</div>
