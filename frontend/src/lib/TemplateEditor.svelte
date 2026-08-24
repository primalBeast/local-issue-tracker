<script lang="ts">
  import { api, type FieldDef, type FieldsDoc } from './api';
  import FieldRenderer from './FieldRenderer.svelte';
  import {
    encodeFieldOrder,
    equalizeLineWidths,
    fieldFlex,
    fieldWidthPercent,
    groupBodyBlocks,
    groupFieldsByRow,
    parseFieldOrder,
    pickField,
    rebalanceLineWidths,
  } from './fieldLayout';
  import { isNotesFillRow } from './panelSize';

  const CONTROL_TYPES = [
    'text',
    'textarea',
    'richtext',
    'select',
    'multiselect',
    'checkbox',
    'number',
    'date',
    'datetime',
  ] as const;

  const RESERVED = new Set(['ticket_key', 'title', 'waiting', 'waiting_for', 'waiting_since', 'notes']);

  type TemplateInfo = {
    id: string;
    name: string;
    origin: string;
    editable: boolean;
    is_default: boolean;
  };

  interface Props {
    projectSlug: string;
    projectName: string;
    onclose: () => void;
    onprojectfields: (doc: FieldsDoc) => void;
  }

  let { projectSlug, projectName, onclose, onprojectfields }: Props = $props();

  let templates = $state<TemplateInfo[]>([]);
  let source = $state<'project' | string>('project');
  let draft = $state<FieldDef[]>([]);
  let version = $state(1);
  let extra = $state<Record<string, unknown>>({});
  let previewValues = $state<Record<string, unknown>>({});
  let busy = $state(false);
  let error = $state('');
  let saveAsOpen = $state(false);
  let saveAsId = $state('');
  let saveAsName = $state('');
  let saveAsDefault = $state(true);
  let saveAsLayout = $state(true);
  let expandedFields = $state<Record<string, boolean>>({});

  let editingProject = $derived(source === 'project');
  let appTemplate = $derived(
    templates.find((t) => t.origin === 'shipped') ?? templates.find((t) => t.is_default)
  );
  let otherTemplates = $derived(templates.filter((t) => t.id !== appTemplate?.id));
  let currentMeta = $derived(templates.find((t) => t.id === source));
  let canSave = $derived(editingProject || Boolean(currentMeta?.editable));
  let previewBlocks = $derived(groupBodyBlocks(groupFieldsByRow(draft)));
  let fieldGroups = $derived.by(() => {
    const map = new Map<number, FieldDef[]>();
    for (const f of draft) {
      const line = lineOf(f);
      const list = map.get(line);
      if (list) list.push(f);
      else map.set(line, [f]);
    }
    return [...map.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([line, fields]) => ({
        line,
        fields: [...fields].sort((a, b) => slotOf(a) - slotOf(b) || a.id.localeCompare(b.id)),
      }));
  });

  async function loadList() {
    const body = await api.templates();
    templates = body.templates;
  }

  async function loadFields() {
    error = '';
    try {
      const doc = editingProject
        ? await api.fields(projectSlug)
        : await api.templateFields(String(source));
      const fields = (doc.fields || []).map((f) => ({
        ...f,
        options: f.options ? [...f.options] : f.options,
      }));
      draft = sortFields(fields);
      version = doc.version ?? 1;
      extra = { ...doc };
      delete extra.fields;
      delete extra.version;
      previewValues = Object.fromEntries(fields.map((f) => [f.id, sampleValue(f)]));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load fields';
    }
  }

  $effect(() => {
    void loadList();
  });

  $effect(() => {
    source;
    void loadFields();
  });

  $effect(() => {
    const next = { ...previewValues };
    let changed = false;
    for (const f of draft) {
      if (!(f.id in next)) {
        next[f.id] = sampleValue(f);
        changed = true;
      } else if (f.type === 'select' && f.options?.length && !f.options.includes(String(next[f.id] ?? ''))) {
        next[f.id] = f.options[0];
        changed = true;
      }
    }
    if (changed) previewValues = next;
  });

  function sampleValue(f: FieldDef): unknown {
    if (f.default !== undefined && f.default !== '') return f.default;
    if (f.type === 'select' && f.options?.[0]) return f.options[0];
    if (f.type === 'multiselect') return [];
    if (f.type === 'checkbox') return false;
    if (f.type === 'number') return 5;
    if (f.type === 'date') return '2026-08-23';
    if (f.type === 'datetime') return '2026-08-23T12:00';
    if (f.type === 'richtext') return { type: 'doc', content: [] };
    if (f.id === 'ticket_key') return 'PROJ-1';
    if (f.id === 'title') return 'Example ticket';
    return '';
  }

  function sortFields(fields: FieldDef[]): FieldDef[] {
    return [...fields].sort((a, b) => {
      const ao = parseFieldOrder(a.order);
      const bo = parseFieldOrder(b.order);
      if (ao.row !== bo.row) return ao.row - bo.row;
      if (ao.col !== bo.col) return ao.col - bo.col;
      return a.id.localeCompare(b.id);
    });
  }

  function lineOf(f: FieldDef): number {
    const row = parseFieldOrder(f.order).row;
    return Number.isFinite(row) && row < Number.MAX_SAFE_INTEGER / 2 ? row : 10;
  }

  function slotOf(f: FieldDef): number {
    return parseFieldOrder(f.order).col + 1;
  }

  function ordinal(n: number): string {
    const v = n % 100;
    if (v >= 11 && v <= 13) return `${n}th`;
    switch (n % 10) {
      case 1:
        return `${n}st`;
      case 2:
        return `${n}nd`;
      case 3:
        return `${n}rd`;
      default:
        return `${n}th`;
    }
  }

  function idx(id: string): number {
    return draft.findIndex((f) => f.id === id);
  }

  function fieldsOnLine(line: number): FieldDef[] {
    return draft.filter((f) => lineOf(f) === line);
  }

  function displayWidth(f: FieldDef): number {
    return Math.round(fieldWidthPercent(f, fieldsOnLine(lineOf(f))));
  }

  function setPlacement(id: string, line: number, slot: number) {
    const i = idx(id);
    if (i < 0) return;
    const prevLine = lineOf(draft[i]);
    const row = Math.max(1, Math.floor(Number(line)) || 1);
    const col = Math.max(1, Math.floor(Number(slot)) || 1) - 1;
    draft[i] = { ...draft[i], order: encodeFieldOrder(row, col) };
    let next = sortFields(draft);
    if (prevLine !== row) {
      next = equalizeLineWidths(next, prevLine);
      next = equalizeLineWidths(next, row);
    }
    draft = next;
  }

  function setWidth(id: string, value: number) {
    const f = draft.find((x) => x.id === id);
    if (!f) return;
    draft = rebalanceLineWidths(draft, lineOf(f), f.id, value);
  }

  function slugify(label: string): string {
    const s = label
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_|_$/g, '')
      .slice(0, 40);
    return s || `field_${Date.now().toString(36)}`;
  }

  function uniqueId(base: string): string {
    let id = base;
    let n = 2;
    const used = new Set(draft.map((f) => f.id));
    while (used.has(id)) {
      id = `${base}_${n}`;
      n += 1;
    }
    return id;
  }

  function addField() {
    const rows = draft.map((f) => lineOf(f)).filter((n) => Number.isFinite(n));
    const order = (rows.length ? Math.max(...rows) : 0) + 10;
    draft = [
      ...draft,
      {
        id: uniqueId('new_field'),
        label: 'New field',
        type: 'text',
        required: false,
        order,
        default: '',
        show_in_list: false,
      },
    ];
  }

  function removeField(id: string) {
    if (!id || RESERVED.has(id)) return;
    draft = draft.filter((f) => f.id !== id);
  }

  function setType(id: string, type: string) {
    const i = idx(id);
    if (i < 0) return;
    const f = { ...draft[i], type };
    if ((type === 'select' || type === 'multiselect') && !f.options?.length) f.options = ['Option 1'];
    draft[i] = f;
    draft = draft;
  }

  function setOptions(id: string, text: string) {
    const i = idx(id);
    if (i < 0) return;
    const options = text
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    draft[i] = { ...draft[i], options };
    draft = draft;
  }

  function toPlain<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T;
  }

  function payload(): FieldsDoc {
    const rest = toPlain(extra) as Record<string, unknown>;
    delete rest.fields;
    delete rest.version;
    return { ...rest, version, fields: toPlain(draft) } as FieldsDoc;
  }

  async function save() {
    if (!canSave) return;
    busy = true;
    error = '';
    try {
      const doc = payload();
      if (editingProject) {
        const saved = await api.putFields(projectSlug, doc);
        onprojectfields(saved);
      } else {
        await api.putTemplateFields(String(source), doc);
      }
      await loadList();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      busy = false;
    }
  }

  function openSaveAs() {
    saveAsId = slugify(projectName);
    saveAsName = projectName;
    saveAsDefault = true;
    saveAsLayout = true;
    saveAsOpen = true;
  }

  async function confirmSaveAs() {
    busy = true;
    error = '';
    try {
      const created = await api.saveTemplate({
        from_project: projectSlug,
        id: saveAsId.trim(),
        name: saveAsName.trim() || saveAsId.trim(),
        set_default: saveAsDefault,
        include_layout: saveAsLayout,
      });
      saveAsOpen = false;
      await loadList();
      source = created.id;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Could not save template';
    } finally {
      busy = false;
    }
  }

  async function makeDefault(id: string) {
    try {
      const body = await api.setDefaultTemplate(id);
      templates = body.templates;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Could not set default';
    }
  }

  function patchPreview(id: string, value: unknown) {
    previewValues = { ...previewValues, [id]: value };
  }

  function toggleField(id: string) {
    expandedFields = { ...expandedFields, [id]: !expandedFields[id] };
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="template-editor" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
  <div class="board-editor-title">Templates</div>
  <p class="template-help">
    Same <strong>Line</strong> number puts controls on one row. <strong>On line</strong> is 1st, 2nd,
    3rd on that row — not a separate row.
  </p>

  <div class="template-source">
    <button type="button" class:current={editingProject} onclick={() => (source = 'project')}>
      Project Template
    </button>
    {#if appTemplate}
      <button
        type="button"
        class:current={!editingProject && source === appTemplate.id}
        onclick={() => (source = appTemplate.id)}
      >
        App Template
      </button>
    {/if}
    {#each otherTemplates as t (t.id)}
      <button type="button" class:current={source === t.id} onclick={() => (source = t.id)}>
        {t.name}
      </button>
    {/each}
  </div>

  {#if error}
    <div class="empty-hint" style="color:var(--danger)">{error}</div>
  {/if}

  {#if !editingProject && currentMeta && !currentMeta.editable}
    <div class="empty-hint">App Template is read-only. Save as Template to make an editable copy.</div>
  {/if}

  <div class="template-split">
    <div class="template-fields">
      {#each fieldGroups as group (group.line)}
        <section class="template-line">
          <div class="template-line-head">
            Line {group.line}
            <span class="template-line-count"
              >{group.fields.length === 1 ? '1 control' : `${group.fields.length} controls`}</span
            >
          </div>
          {#each group.fields as f (f.id)}
            <div class="template-field" class:open={expandedFields[f.id]}>
              <div class="template-field-top">
                <button
                  type="button"
                  class="ghost template-field-toggle"
                  class:open={expandedFields[f.id]}
                  title={expandedFields[f.id] ? 'Hide details' : 'Show details'}
                  aria-expanded={Boolean(expandedFields[f.id])}
                  onclick={() => toggleField(f.id)}
                >
                  ▾
                </button>
                <input
                  type="text"
                  bind:value={f.label}
                  oninput={(e) => {
                    f.label = e.currentTarget.value;
                    draft = draft;
                  }}
                  disabled={!canSave}
                />
                <select
                  value={f.type}
                  disabled={!canSave || RESERVED.has(f.id)}
                  onchange={(e) => setType(f.id, e.currentTarget.value)}
                >
                  {#each CONTROL_TYPES as t}
                    <option value={t}>{t}</option>
                  {/each}
                </select>
                <span class="template-field-summary">{ordinal(slotOf(f))} · {displayWidth(f)}%</span>
              </div>
              {#if expandedFields[f.id]}
                <div class="template-field-extra">
                  <label class="template-place">
                    Line
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={lineOf(f)}
                      disabled={!canSave}
                      oninput={(e) => setPlacement(f.id, Number(e.currentTarget.value), slotOf(f))}
                    />
                  </label>
                  <label class="template-place">
                    On line
                    <select
                      value={slotOf(f)}
                      disabled={!canSave}
                      onchange={(e) => setPlacement(f.id, lineOf(f), Number(e.currentTarget.value))}
                    >
                      {#each [1, 2, 3, 4, 5, 6] as n}
                        <option value={n}>{ordinal(n)}</option>
                      {/each}
                    </select>
                  </label>
                  <label class="template-place">
                    Width
                    <input
                      type="number"
                      min="5"
                      max="100"
                      step="1"
                      value={displayWidth(f)}
                      disabled={!canSave}
                      oninput={(e) => setWidth(f.id, Number(e.currentTarget.value))}
                    />
                    %
                  </label>
                  <label class="check-row">
                    <input
                      type="checkbox"
                      checked={Boolean(f.width_lock)}
                      disabled={!canSave}
                      onchange={(e) => {
                        f.width_lock = e.currentTarget.checked;
                        draft = draft;
                      }}
                    />
                    Lock Width
                  </label>
                  <label class="check-row">
                    <input
                      type="checkbox"
                      checked={Boolean(f.required)}
                      disabled={!canSave}
                      onchange={(e) => {
                        f.required = e.currentTarget.checked;
                        draft = draft;
                      }}
                    />
                    Required
                  </label>
                  <label class="check-row">
                    <input
                      type="checkbox"
                      checked={Boolean(f.show_in_list)}
                      disabled={!canSave}
                      onchange={(e) => {
                        f.show_in_list = e.currentTarget.checked;
                        draft = draft;
                      }}
                    />
                    All Items
                  </label>
                  {#if !RESERVED.has(f.id)}
                    <button type="button" class="ghost" disabled={!canSave} onclick={() => removeField(f.id)}
                      >Remove</button
                    >
                  {/if}
                </div>
                {#if f.type === 'select' || f.type === 'multiselect'}
                  <textarea
                    rows="3"
                    disabled={!canSave}
                    value={(f.options || []).join('\n')}
                    oninput={(e) => setOptions(f.id, e.currentTarget.value)}
                    placeholder="One option per line"
                  ></textarea>
                {/if}
              {/if}
            </div>
          {/each}
        </section>
      {/each}
    </div>

    <div class="template-preview">
      <div class="template-preview-label">Example panel</div>
      <div class="panel template-preview-panel">
        <div class="panel-header">
          <div class="panel-title">Example ticket</div>
        </div>
        <div class="panel-body">
          {#each previewBlocks as block (block.kind === 'waiting' ? 'waiting' : block.row.row)}
            {#if block.kind === 'waiting'}
              {@const person = pickField(block.fields, 'waiting_for')}
              {@const since = pickField(block.fields, 'waiting_since')}
              {@const waitingOn = Boolean(previewValues.waiting)}
              {#if previewValues.state !== 'Done'}
                <div class="waiting-block">
                  <label class="check-row">
                    <input
                      type="checkbox"
                      checked={waitingOn}
                      onchange={(e) => patchPreview('waiting', e.currentTarget.checked)}
                    />
                    {pickField(block.fields, 'waiting')?.label || 'Waiting for...'}
                  </label>
                  {#if waitingOn}
                    <div class="waiting-details">
                      {#if person}
                        <label class="waiting-inline">
                          <span>Name:</span>
                          <input
                            type="text"
                            value={String(previewValues.waiting_for ?? '')}
                            oninput={(e) => patchPreview('waiting_for', e.currentTarget.value)}
                          />
                        </label>
                      {/if}
                      {#if since}
                        <label class="waiting-inline">
                          <span>Since:</span>
                          <input
                            type="date"
                            value={String(previewValues.waiting_since ?? '')}
                            oninput={(e) => patchPreview('waiting_since', e.currentTarget.value)}
                          />
                        </label>
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
                  <div class="field-col" style:flex={`${fieldFlex(def, block.row.fields)} 1 0`}>
                    <FieldRenderer
                      {def}
                      fill={isNotesFillRow(block.row)}
                      fields={previewValues}
                      onchange={patchPreview}
                    />
                  </div>
                {/each}
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  </div>

  <div class="board-editor-actions">
    <button type="button" class="ghost" disabled={!canSave} onclick={addField}>Add field</button>
    <span class="board-editor-actions-spacer"></span>
    <button type="button" class="ghost" onclick={onclose}>Close</button>
    {#if editingProject}
      <button type="button" onclick={openSaveAs}>Save as Template…</button>
    {/if}
    {#if !editingProject && currentMeta?.editable}
      <button type="button" class="ghost" onclick={() => void makeDefault(currentMeta.id)}>Use for new projects</button>
    {/if}
    <button type="button" class="primary" disabled={!canSave || busy} onclick={() => void save()}>Save</button>
  </div>

  {#if saveAsOpen}
    <div class="template-saveas">
      <div class="project-section-title">Save as Template</div>
      <label class="field-label" for="tpl-id">Id</label>
      <input id="tpl-id" type="text" bind:value={saveAsId} placeholder="issue-tracker" />
      <label class="field-label" for="tpl-name" style="margin-top:8px">Name</label>
      <input id="tpl-name" type="text" bind:value={saveAsName} />
      <label class="check-row" style="margin-top:8px">
        <input type="checkbox" bind:checked={saveAsDefault} />
        Use for new projects
      </label>
      <label class="check-row">
        <input type="checkbox" bind:checked={saveAsLayout} />
        Include Main Board layout (no tickets)
      </label>
      <div class="board-editor-actions">
        <button type="button" class="ghost" onclick={() => (saveAsOpen = false)}>Cancel</button>
        <button type="button" class="primary" disabled={busy || !saveAsId.trim()} onclick={() => void confirmSaveAs()}>
          Save template
        </button>
      </div>
    </div>
  {/if}
</div>
