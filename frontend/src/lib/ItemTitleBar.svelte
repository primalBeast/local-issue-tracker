<script lang="ts">
  interface Props {
    ticketKey: string;
    description: string;
    keyFieldLabel?: string;
    descriptionLabel?: string;
    onTicketKey: (value: string) => void;
    onDescription: (value: string) => void;
    /** When set, double-clicking the ticket number opens this URL. */
    ticketLaunchHref?: string | null;
  }

  let {
    ticketKey,
    description,
    keyFieldLabel = 'Ticket number',
    descriptionLabel = 'Description',
    onTicketKey,
    onDescription,
    ticketLaunchHref = null,
  }: Props = $props();

  let descTrimmed = $derived(String(description ?? '').trim());
  /** Stay open while typing. Only collapse after leaving the editor with a description. */
  let editing = $state(!String(description ?? '').trim());

  function keyLabel(): string {
    return String(ticketKey ?? '').trim() || 'Untitled';
  }

  function onKeyDblClick(e: MouseEvent) {
    const href = String(ticketLaunchHref ?? '').trim();
    if (!href) return;
    e.preventDefault();
    e.stopPropagation();
    window.open(href, '_blank', 'noopener,noreferrer');
  }

  function toggle(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!descTrimmed) {
      editing = true;
      return;
    }
    editing = !editing;
  }

  function onEditorFocusOut(e: FocusEvent) {
    const root = e.currentTarget as HTMLElement;
    const next = e.relatedTarget as Node | null;
    if (next && root.contains(next)) return;
    if (String(description ?? '').trim()) editing = false;
  }
</script>

<div class="item-title-bar">
  <div class="item-title-row">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="item-title-key"
      class:launchable={!!ticketLaunchHref}
      title={ticketLaunchHref ? 'Open ticket URL' : undefined}
      ondblclick={onKeyDblClick}
    >
      {keyLabel()}
    </div>
    {#if descTrimmed}
      <div class="item-title-desc" title={descTrimmed}>{descTrimmed}</div>
    {/if}
    <button
      type="button"
      class="ghost item-title-toggle"
      class:open={editing}
      title={descTrimmed ? 'Edit ticket number and description' : 'Add a description'}
      aria-expanded={editing}
      onclick={toggle}
    >
      ▾
    </button>
  </div>
  {#if editing}
    <div class="item-title-editor" onfocusout={onEditorFocusOut}>
      <label class="item-title-field">
        <span class="field-label">{keyFieldLabel}</span>
        <input
          type="text"
          value={ticketKey}
          placeholder="PROJ-123"
          autocomplete="off"
          oninput={(e) => onTicketKey(e.currentTarget.value)}
        />
      </label>
      <label class="item-title-field">
        <span class="field-label">{descriptionLabel}</span>
        <input
          type="text"
          value={description}
          placeholder="Short description"
          autocomplete="off"
          oninput={(e) => onDescription(e.currentTarget.value)}
          onkeydown={(e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            editing = false;
            const panel = (e.currentTarget as HTMLElement).closest('.panel');
            queueMicrotask(() => {
              const notes = panel?.querySelector(
                '.field-row-fill .ProseMirror, .field-group-fill .ProseMirror, .rte .ProseMirror'
              ) as HTMLElement | null;
              notes?.focus();
            });
          }}
        />
      </label>
    </div>
  {/if}
</div>
