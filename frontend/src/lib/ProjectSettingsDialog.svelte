<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    resolveSettingsClose,
    settingsDraftFromProject,
    URL_PREFIX_HINT,
    URL_PREFIX_PLACEHOLDER,
    type SettingsDraft,
  } from './projectMenu';

  interface Props {
    name: string;
    ticketPrefix: string;
    urlPrefix: string;
    onsave: (draft: SettingsDraft) => void;
    onclose: () => void;
  }

  let { name, ticketPrefix, urlPrefix, onsave, onclose }: Props = $props();

  // Keep the values from open. A later prop change must not wipe in-progress edits.
  // svelte-ignore state_referenced_locally
  const baseline = settingsDraftFromProject({
    name,
    ticket_prefix: ticketPrefix,
    url_prefix: urlPrefix,
  });
  // svelte-ignore state_referenced_locally
  let draft = $state({ ...baseline });
  let nameEl = $state<HTMLInputElement | null>(null);

  function dismiss(reason: 'save' | 'cancel' | 'escape') {
    const result = resolveSettingsClose(baseline, draft, reason);
    if (result.persist) onsave(result.persist);
    else onclose();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    dismiss('escape');
  }

  onMount(() => {
    void tick().then(() => nameEl?.focus());
  });
</script>

<div class="confirm-backdrop" role="presentation">
  <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
  <div
    class="confirm-dialog project-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="project-settings-title"
    tabindex="-1"
    onkeydown={onKeydown}
  >
    <div class="board-editor-title" id="project-settings-title">Project settings</div>
    <form
      onsubmit={(e) => {
        e.preventDefault();
        dismiss('save');
      }}
    >
      <div class="project-dialog-field">
        <label class="field-label" for="settings-project-name">Name</label>
        <input id="settings-project-name" type="text" bind:this={nameEl} bind:value={draft.name} />
      </div>
      <div class="project-dialog-field">
        <label class="field-label" for="settings-ticket-prefix">Ticket prefix</label>
        <input
          id="settings-ticket-prefix"
          type="text"
          placeholder="NEW-"
          bind:value={draft.ticketPrefix}
        />
      </div>
      <div class="project-dialog-field">
        <label class="field-label" for="settings-url-prefix">URL prefix</label>
        <input
          id="settings-url-prefix"
          type="text"
          placeholder={URL_PREFIX_PLACEHOLDER}
          aria-describedby="settings-url-prefix-hint"
          bind:value={draft.urlPrefix}
        />
        <p class="project-field-hint" id="settings-url-prefix-hint">{URL_PREFIX_HINT}</p>
      </div>
      <div class="board-editor-actions">
        <button type="button" class="ghost" onclick={() => dismiss('cancel')}>Cancel</button>
        <button type="submit" class="primary">Save</button>
      </div>
    </form>
  </div>
</div>
