<script lang="ts">
  import type { FieldDef } from './api';
  import { CONTROL_TYPES, RESERVED } from './templateFields';
  import { placementPhrase } from './templateLabels';
  import { displayWidth } from './templatePlacement';

  interface Props {
    field: FieldDef | null;
    fields: FieldDef[];
    disabled: boolean;
    onpatch: (id: string, patch: Partial<FieldDef>) => void;
    onsettype: (id: string, type: string) => void;
    onsetoptions: (id: string, text: string) => void;
    onsetwidth: (id: string, width: number) => void;
    onmove: (id: string, action: 'earlier' | 'later' | 'prev-row' | 'next-row' | 'new-row') => void;
    onremove: (id: string) => void;
  }

  let {
    field,
    fields,
    disabled,
    onpatch,
    onsettype,
    onsetoptions,
    onsetwidth,
    onmove,
    onremove,
  }: Props = $props();
</script>

<div class="template-details">
  <div class="template-preview-label">Field</div>
  {#if !field}
    <div class="empty-hint">Select a field to edit it.</div>
  {:else}
    <p class="template-details-place">{placementPhrase(field, fields)}</p>
    <label class="field-label" for="tpl-field-label">Name</label>
    <input
      id="tpl-field-label"
      type="text"
      value={field.label}
      disabled={disabled}
      oninput={(e) => onpatch(field.id, { label: e.currentTarget.value })}
    />
    <label class="field-label" for="tpl-field-type">Type</label>
    <select
      id="tpl-field-type"
      value={field.type}
      disabled={disabled || RESERVED.has(field.id)}
      onchange={(e) => onsettype(field.id, e.currentTarget.value)}
    >
      {#each CONTROL_TYPES as t}
        <option value={t}>{t}</option>
      {/each}
    </select>
    {#if field.type === 'select' || field.type === 'multiselect'}
      <label class="field-label" for="tpl-field-options">Options</label>
      <textarea
        id="tpl-field-options"
        rows="3"
        disabled={disabled}
        value={(field.options || []).join('\n')}
        oninput={(e) => onsetoptions(field.id, e.currentTarget.value)}
        placeholder="One option per line"
      ></textarea>
    {/if}
    <label class="field-label" for="tpl-field-width">Width</label>
    <div class="template-place">
      <input
        id="tpl-field-width"
        type="number"
        min="5"
        max="100"
        step="1"
        value={displayWidth(field, fields)}
        disabled={disabled}
        oninput={(e) => onsetwidth(field.id, Number(e.currentTarget.value))}
      />
      %
    </div>
    <div class="template-details-moves">
      <button type="button" class="ghost" disabled={disabled} onclick={() => onmove(field.id, 'earlier')}
        >Earlier in row</button
      >
      <button type="button" class="ghost" disabled={disabled} onclick={() => onmove(field.id, 'later')}
        >Later in row</button
      >
      <button type="button" class="ghost" disabled={disabled} onclick={() => onmove(field.id, 'prev-row')}
        >Previous row</button
      >
      <button type="button" class="ghost" disabled={disabled} onclick={() => onmove(field.id, 'next-row')}
        >Next row</button
      >
      <button type="button" class="ghost" disabled={disabled} onclick={() => onmove(field.id, 'new-row')}
        >New row</button
      >
    </div>
    <label class="check-row">
      <input
        type="checkbox"
        checked={Boolean(field.width_lock)}
        disabled={disabled}
        onchange={(e) => onpatch(field.id, { width_lock: e.currentTarget.checked })}
      />
      Lock width
    </label>
    <label class="check-row">
      <input
        type="checkbox"
        checked={Boolean(field.required)}
        disabled={disabled}
        onchange={(e) => onpatch(field.id, { required: e.currentTarget.checked })}
      />
      Required
    </label>
    {#if !RESERVED.has(field.id)}
      <button type="button" class="ghost" disabled={disabled} onclick={() => onremove(field.id)}>Remove</button>
    {/if}
  {/if}
</div>
