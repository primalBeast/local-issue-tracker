<script lang="ts">
  import type { FieldDef } from './api';
  import { waitingNameChoices } from './waiting';

  interface Props {
    def: FieldDef;
    value: unknown;
    display: string;
    editing: boolean;
    onCommit: (value: unknown) => void;
    onEnd: () => void;
  }

  let { def, value, display, editing, onCommit, onEnd }: Props = $props();

  function selectOptions(): string[] {
    return waitingNameChoices(def.options, value);
  }

  let selectSize = $derived(
    Math.max(1, selectOptions().length + (def.required ? 0 : 1))
  );

  let selectBoxEl = $state<HTMLDivElement | undefined>(undefined);

  $effect(() => {
    if (!editing || def.type !== 'select') return;
    const el = selectBoxEl;
    if (!el) return;
    el.focus();
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  });

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Tab') {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (e.key !== 'Enter' && e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as HTMLElement).blur();
  }

  function pickSelect(opt: string) {
    onCommit(opt);
    onEnd();
  }

  function commitNumber(raw: string) {
    onCommit(raw === '' ? null : Number(raw));
  }

  function tryShowPicker(el: EventTarget | null) {
    const picker = el as { showPicker?: () => void };
    try {
      picker.showPicker?.();
    } catch {
      /* not a picker, or already open */
    }
  }
</script>

{#if editing}
  {#if def.type === 'select'}
    <div
      class="list-cell-edit list-cell-select"
      style={`--list-select-size:${selectSize}`}
      role="listbox"
      tabindex="0"
      bind:this={selectBoxEl}
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onblur={onEnd}
      onkeydown={onKey}
    >
      {#if !def.required}
        <button
          type="button"
          class="list-select-opt"
          class:selected={value == null || value === ''}
          role="option"
          aria-label="Clear"
          aria-selected={value == null || value === ''}
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => pickSelect('')}
        ></button>
      {/if}
      {#each selectOptions() as opt}
        <button
          type="button"
          class="list-select-opt"
          class:selected={String(value ?? '') === opt}
          role="option"
          aria-selected={String(value ?? '') === opt}
          onpointerdown={(e) => e.preventDefault()}
          onclick={() => pickSelect(opt)}
        >{opt}</button>
      {/each}
    </div>
  {:else if def.type === 'number'}
    <input
      class="list-cell-edit"
      type="number"
      min={def.validation?.min as number | undefined}
      max={def.validation?.max as number | undefined}
      step={(def.validation?.step as number | undefined) ?? 1}
      value={value as number}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => commitNumber(e.currentTarget.value)}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {:else if def.type === 'checkbox'}
    <input
      class="list-cell-edit"
      type="checkbox"
      checked={Boolean(value)}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onchange={(e) => {
        onCommit(e.currentTarget.checked);
        onEnd();
      }}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {:else if def.type === 'date'}
    <input
      class="list-cell-edit"
      type="date"
      value={String(value ?? '')}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onfocus={(e) => tryShowPicker(e.currentTarget)}
      oninput={(e) => onCommit(e.currentTarget.value)}
      onchange={(e) => onCommit(e.currentTarget.value)}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {:else if def.type === 'datetime'}
    <input
      class="list-cell-edit"
      type="datetime-local"
      value={String(value ?? '')}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => onCommit(e.currentTarget.value)}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {:else}
    <input
      class="list-cell-edit"
      type="text"
      value={String(value ?? '')}
      autofocus
      onpointerdown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      oninput={(e) => onCommit(e.currentTarget.value)}
      onblur={onEnd}
      onkeydown={onKey}
    />
  {/if}
{:else}
  <span class="list-cell-label">{display}</span>
{/if}
