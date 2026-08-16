<script lang="ts">
  import type { FieldDef } from './api';
  import { isVisible } from './filters';
  import RichText from './RichText.svelte';

  interface Props {
    def: FieldDef;
    fields: Record<string, unknown>;
    onchange: (id: string, value: unknown) => void;
    fill?: boolean;
  }

  let { def, fields, onchange, fill = false }: Props = $props();

  let visible = $derived(isVisible(def, fields));
  let value = $derived(fields[def.id]);
</script>

{#if visible}
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
        value={value as number}
        oninput={(e) => onchange(def.id, e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}
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
