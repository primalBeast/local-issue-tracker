<script lang="ts">
  import type { FieldDef } from './api';
  import FieldRenderer from './FieldRenderer.svelte';
  import ItemTitleBar from './ItemTitleBar.svelte';
  import { fieldFlex, groupBodyBlocks, groupFieldsByRow, pickField } from './fieldLayout';
  import { isNotesFillRow } from './panelSize';
  import { TITLE_EDITOR_IDS } from './templateFields';
  import { fieldIdFromTitleBarClick, isSelected } from './templateSelection';
  import { waitingNameChoices } from './waiting';

  interface Props {
    draft: FieldDef[];
    previewValues: Record<string, unknown>;
    selectedId: string | null;
    onselect: (id: string) => void;
    onpreview: (id: string, value: unknown) => void;
  }

  let { draft, previewValues, selectedId, onselect, onpreview }: Props = $props();

  let previewBlocks = $derived(
    groupBodyBlocks(groupFieldsByRow(draft.filter((f) => !TITLE_EDITOR_IDS.has(f.id))))
  );
  let keyFieldLabel = $derived(draft.find((f) => f.id === 'ticket_key')?.label || 'Ticket number');
  let descriptionLabel = $derived(draft.find((f) => f.id === 'title')?.label || 'Description');
  let alternateLabel = $derived(draft.find((f) => f.id === 'alternate_ticket')?.label || 'Alternate ticket');

  function selectLabel(name: string): string {
    return `Select field ${name}`;
  }

  function onHitKey(e: KeyboardEvent) {
    if (e.target !== e.currentTarget) return;
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).click();
  }
</script>

<div class="template-preview">
  <div class="template-preview-label">Example panel</div>
  <div class="panel template-preview-panel">
    <div class="panel-header">
      <div
        class="panel-title-slot template-preview-hit"
        class:is-selected={isSelected(selectedId, 'ticket_key') ||
          isSelected(selectedId, 'title') ||
          isSelected(selectedId, 'alternate_ticket')}
        data-field-id="ticket_key"
        role="button"
        tabindex="0"
        aria-label={selectLabel(`${keyFieldLabel}, ${descriptionLabel}, or ${alternateLabel}`)}
        onclick={(e) =>
          onselect(fieldIdFromTitleBarClick(e.target, { ticket: keyFieldLabel, title: descriptionLabel, alternate: alternateLabel }))}
        onkeydown={onHitKey}
      >
        <ItemTitleBar
          ticketKey={String(previewValues.ticket_key ?? '')}
          description={String(previewValues.title ?? '')}
          alternateTicket={String(previewValues.alternate_ticket ?? '')}
          {keyFieldLabel}
          {descriptionLabel}
          {alternateLabel}
          onTicketKey={(value) => onpreview('ticket_key', value)}
          onDescription={(value) => onpreview('title', value)}
          onAlternateTicket={(value) => onpreview('alternate_ticket', value)}
        />
      </div>
    </div>
    <div class="panel-body">
      {#each previewBlocks as block (block.kind === 'waiting' ? 'waiting' : block.row.row)}
        {#if block.kind === 'waiting'}
          {@const person = pickField(block.fields, 'waiting_for')}
          {@const since = pickField(block.fields, 'waiting_since')}
          {@const waitingOn = Boolean(previewValues.waiting)}
          {#if previewValues.state !== 'Done'}
            <div class="waiting-block">
              <div
                class="template-preview-hit"
                class:is-selected={isSelected(selectedId, 'waiting')}
                data-field-id="waiting"
                role="button"
                tabindex="0"
                aria-label={selectLabel(draft.find((f) => f.id === 'waiting')?.label || 'Waiting for…')}
                onclick={() => onselect('waiting')}
                onkeydown={onHitKey}
              >
                <label class="check-row">
                  <input
                    type="checkbox"
                    checked={waitingOn}
                    onchange={(e) => onpreview('waiting', e.currentTarget.checked)}
                  />
                  Waiting for…
                </label>
              </div>
              {#if waitingOn}
                <div class="waiting-details">
                  {#if since}
                    <div
                      class="template-preview-hit"
                      class:is-selected={isSelected(selectedId, 'waiting_since')}
                      data-field-id="waiting_since"
                      role="button"
                      tabindex="0"
                      aria-label={selectLabel(since.label || 'Since')}
                      onclick={() => onselect('waiting_since')}
                      onkeydown={onHitKey}
                    >
                      <label class="waiting-inline">
                        <span>Since:</span>
                        <input
                          type="date"
                          value={String(previewValues.waiting_since ?? '')}
                          oninput={(e) => onpreview('waiting_since', e.currentTarget.value)}
                        />
                      </label>
                    </div>
                  {/if}
                  {#if person}
                    <div
                      class="template-preview-hit"
                      class:is-selected={isSelected(selectedId, 'waiting_for')}
                      data-field-id="waiting_for"
                      role="button"
                      tabindex="0"
                      aria-label={selectLabel(person.label || 'Name')}
                      onclick={() => onselect('waiting_for')}
                      onkeydown={onHitKey}
                    >
                      <label class="waiting-inline">
                        <span>{person.label || 'Name'}:</span>
                        <select
                          value={String(previewValues.waiting_for ?? '')}
                          onchange={(e) => onpreview('waiting_for', e.currentTarget.value)}
                        >
                          <option value=""></option>
                          {#each waitingNameChoices(person.options, previewValues.waiting_for) as opt}
                            <option value={opt}>{opt}</option>
                          {/each}
                        </select>
                      </label>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {:else}
          <div
            class="field-row"
            class:field-row-multi={block.row.fields.length > 1}
            class:field-row-fill={isNotesFillRow(block.row)}
          >
            {#each block.row.fields as def (def.id)}
              <div
                class="field-col template-preview-hit"
                class:is-selected={isSelected(selectedId, def.id)}
                data-field-id={def.id}
                role="button"
                tabindex="0"
                aria-label={selectLabel(def.label || def.id)}
                style:flex={`${fieldFlex(def, block.row.fields)} 1 0`}
                onclick={() => onselect(def.id)}
                onkeydown={onHitKey}
              >
                <FieldRenderer {def} fill={isNotesFillRow(block.row)} fields={previewValues} onchange={onpreview} />
              </div>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  </div>
</div>
