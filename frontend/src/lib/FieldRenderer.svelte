<script lang="ts">
  import type { FieldDef } from './api';
  import { isVisible } from './filters';
  import RichText from './RichText.svelte';
  import UrlTicketField from './UrlTicketField.svelte';

  interface Props {
    def: FieldDef;
    fields: Record<string, unknown>;
    onchange: (id: string, value: unknown) => void;
    fill?: boolean;
    addSlot?: boolean;
    onAddSlot?: () => void;
  }

  let { def, fields, onchange, fill = false, addSlot = false, onAddSlot }: Props = $props();

  let visible = $derived(isVisible(def, fields));
  let value = $derived(fields[def.id]);
  let numberFocused = $state(false);
  let numberDraft = $state('');
  let numberOriginal: unknown = undefined;

  function numberShown(): string {
    if (numberFocused) return numberDraft;
    if (value == null || value === '') return '';
    return String(value);
  }

  function beginNumberEdit() {
    if (numberFocused) return;
    numberFocused = true;
    numberOriginal = value;
    numberDraft = value == null || value === '' ? '' : String(value);
  }

  function numberIsValid(raw: string): { ok: true; value: number } | { ok: false } {
    if (raw.trim() === '') return { ok: false };
    const n = Number(raw);
    if (!Number.isFinite(n)) return { ok: false };
    const min = def.validation?.min;
    const max = def.validation?.max;
    if (typeof min === 'number' && n < min) return { ok: false };
    if (typeof max === 'number' && n > max) return { ok: false };
    return { ok: true, value: n };
  }

  function finishNumberEdit() {
    if (!numberFocused) return;
    const parsed = numberIsValid(numberDraft);
    numberFocused = false;
    if (!parsed.ok) return;
    if (numberOriginal == null || numberOriginal === '' || Number(numberOriginal) !== parsed.value) {
      onchange(def.id, parsed.value);
    }
  }
</script>

{#if visible}
  {#if def.type === 'url'}
    <UrlTicketField
      id={def.id}
      label={def.label}
      value={String(value ?? '')}
      placeholder={def.placeholder || 'Full URL'}
      showAdd={addSlot}
      onchange={(v) => onchange(def.id, v)}
      onAdd={onAddSlot}
    />
  {:else}
  <div class="field-group" class:field-group-fill={fill}>
    <label class="field-label" for={def.id}>{def.label}{def.required ? ' *' : ''}</label>

    {#if def.type === 'text'}
      <input
        id={def.id}
        type="text"
        placeholder={def.placeholder || ''}
        value={String(value ?? '')}
        oninput={(e) => onchange(def.id, e.currentTarget.value)}
      />
    {:else if def.type === 'textarea'}
      <textarea
        id={def.id}
        rows="3"
        value={String(value ?? '')}
        oninput={(e) => onchange(def.id, e.currentTarget.value)}
      ></textarea>
    {:else if def.type === 'number'}
      <input
        id={def.id}
        type="number"
        min={def.validation?.min as number | undefined}
        max={def.validation?.max as number | undefined}
        step={(def.validation?.step as number | undefined) ?? 1}
        value={numberShown()}
        onfocus={beginNumberEdit}
        oninput={(e) => {
          if (!numberFocused) beginNumberEdit();
          numberDraft = e.currentTarget.value;
        }}
        onblur={finishNumberEdit}
      />
    {:else if def.type === 'select'}
      <select
        id={def.id}
        value={String(value ?? '')}
        onchange={(e) => onchange(def.id, e.currentTarget.value)}
      >
        {#each def.options || [] as opt}
          <option value={opt}>{opt}</option>
        {/each}
      </select>
    {:else if def.type === 'checkbox'}
      <label class="check-row">
        <input
          id={def.id}
          type="checkbox"
          checked={Boolean(value)}
          onchange={(e) => onchange(def.id, e.currentTarget.checked)}
        />
        {def.label}
      </label>
    {:else if def.type === 'date'}
      <input
        id={def.id}
        type="date"
        value={String(value ?? '')}
        oninput={(e) => onchange(def.id, e.currentTarget.value)}
        onchange={(e) => onchange(def.id, e.currentTarget.value)}
      />
    {:else if def.type === 'datetime'}
      <input
        id={def.id}
        type="datetime-local"
        value={String(value ?? '')}
        oninput={(e) => onchange(def.id, e.currentTarget.value)}
      />
    {:else if def.type === 'multiselect'}
      <div class="multi">
        {#each def.options || [] as opt}
          <label class="check-row">
            <input
              type="checkbox"
              checked={Array.isArray(value) && (value as string[]).includes(opt)}
              onchange={(e) => {
                const cur = Array.isArray(value) ? [...(value as string[])] : [];
                if (e.currentTarget.checked) cur.push(opt);
                else {
                  const i = cur.indexOf(opt);
                  if (i >= 0) cur.splice(i, 1);
                }
                onchange(def.id, cur);
              }}
            />
            {opt}
          </label>
        {/each}
      </div>
    {:else if def.type === 'richtext'}
      <RichText fill={fill} value={value} onchange={(json) => onchange(def.id, json)} />
    {:else}
      <input
        id={def.id}
        type="text"
        value={String(value ?? '')}
        oninput={(e) => onchange(def.id, e.currentTarget.value)}
      />
    {/if}

    {#if def.help_text}
      <div style="color:var(--text-faint);font-size:11px;margin-top:3px">{def.help_text}</div>
    {/if}
  </div>
  {/if}
{/if}
