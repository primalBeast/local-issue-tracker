<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { DISCARD_LABEL, DISCARD_PROMPT, KEEP_LABEL } from './templateCloseGuard';
  import { handleFocusTrap } from './templateFocusTrap';

  interface Props {
    ondiscard: () => void;
    onkeep: () => void;
  }

  let { ondiscard, onkeep }: Props = $props();

  let dialogEl = $state<HTMLDivElement | null>(null);
  let keepEl = $state<HTMLButtonElement | null>(null);

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Tab' && dialogEl) handleFocusTrap(dialogEl, e);
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    onkeep();
  }

  onMount(() => {
    void tick().then(() => keepEl?.focus());
  });
</script>

<div class="confirm-backdrop template-discard-backdrop" role="presentation">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="confirm-dialog"
    bind:this={dialogEl}
    role="dialog"
    aria-modal="true"
    aria-labelledby="template-discard-title"
    tabindex="-1"
    onkeydown={onKeydown}
  >
    <div class="board-editor-title" id="template-discard-title">{DISCARD_PROMPT}</div>
    <div class="board-editor-actions">
      <button type="button" class="ghost" onclick={ondiscard}>{DISCARD_LABEL}</button>
      <button type="button" class="primary" bind:this={keepEl} onclick={onkeep}>{KEEP_LABEL}</button>
    </div>
  </div>
</div>
