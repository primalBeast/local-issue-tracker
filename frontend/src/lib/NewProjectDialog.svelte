<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    initialNewProjectDraft,
    templateOptionLabel,
    type NewProjectDraft,
    type TemplateOption,
  } from './projectMenu';

  interface Props {
    templates: TemplateOption[];
    defaultTemplateId: string;
    oncreate: (draft: NewProjectDraft) => void;
    onclose: () => void;
  }

  let { templates, defaultTemplateId, oncreate, onclose }: Props = $props();

  let draft = $state(initialNewProjectDraft());
  let touchedTemplate = false;
  let nameEl = $state<HTMLInputElement | null>(null);

  $effect(() => {
    if (touchedTemplate) return;
    const next = defaultTemplateId || 'issue-tracker';
    if (draft.templateId !== next) draft.templateId = next;
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    onclose();
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
    aria-labelledby="new-project-title"
    tabindex="-1"
    onkeydown={onKeydown}
  >
    <div class="board-editor-title" id="new-project-title">New project</div>
    <form
      onsubmit={(e) => {
        e.preventDefault();
        oncreate(draft);
      }}
    >
      <div class="project-dialog-field">
        <label class="field-label" for="new-project-name">Name</label>
        <input id="new-project-name" type="text" bind:this={nameEl} bind:value={draft.name} />
      </div>
      <div class="project-dialog-field">
        <label class="field-label" for="new-project-prefix">Ticket prefix</label>
        <input
          id="new-project-prefix"
          type="text"
          placeholder="NEW-"
          bind:value={draft.ticketPrefix}
        />
      </div>
      {#if templates.length}
        <div class="project-dialog-field">
          <label class="field-label" for="new-project-template">Template</label>
          <select
            id="new-project-template"
            bind:value={draft.templateId}
            onchange={() => (touchedTemplate = true)}
          >
            {#each templates as t (t.id)}
              <option value={t.id}>{templateOptionLabel(t)}</option>
            {/each}
          </select>
        </div>
      {/if}
      <div class="board-editor-actions">
        <button type="button" class="ghost" onclick={() => onclose()}>Cancel</button>
        <button type="submit" class="primary">Create</button>
      </div>
    </form>
  </div>
</div>
