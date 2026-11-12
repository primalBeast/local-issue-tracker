<script lang="ts">
  import { BUILTIN_LABEL, DEFAULT_BADGE, PROJECT_FIELDS_LABEL } from './templateLabels';
  import { listEntries, type TemplateInfo, type TemplateSource } from './templateListModel';

  interface Props {
    templates: TemplateInfo[];
    source: TemplateSource;
    onselect: (source: TemplateSource) => void;
    onsetdefault?: (id: string) => void;
  }

  let { templates, source, onselect, onsetdefault }: Props = $props();

  let entries = $derived(listEntries(templates, source));
  let builtin = $derived(entries.builtin);
  let selectedSaved = $derived(entries.saved.find((t) => t.selected));
</script>

<nav class="template-list" aria-label="Templates">
  <div class="template-list-group">
    <button
      type="button"
      class="template-list-item"
      class:current={entries.project.selected}
      onclick={() => onselect('project')}
    >
      {PROJECT_FIELDS_LABEL}
    </button>
  </div>

  {#if builtin}
    <div class="template-list-group">
      <button
        type="button"
        class="template-list-item"
        class:current={builtin.selected}
        onclick={() => {
          if (builtin) onselect(builtin.id);
        }}
      >
        <span>{BUILTIN_LABEL}</span>
        {#if builtin.badge}
          <span class="template-list-badge">{builtin.badge}</span>
        {/if}
      </button>
    </div>
  {/if}

  {#if entries.saved.length}
    <div class="template-list-group">
      <div class="template-list-heading">Saved templates</div>
      {#each entries.saved as t (t.id)}
        <button
          type="button"
          class="template-list-item"
          class:current={t.selected}
          onclick={() => onselect(t.id)}
        >
          <span>{t.label}</span>
          {#if t.badge}
            <span class="template-list-badge">{t.badge}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}

  {#if selectedSaved && !selectedSaved.readOnly && !selectedSaved.badge && onsetdefault}
    <button type="button" class="ghost template-list-default" onclick={() => onsetdefault(selectedSaved!.id)}>
      {DEFAULT_BADGE}
    </button>
  {/if}
</nav>
