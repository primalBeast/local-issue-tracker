<script lang="ts">
  import { api, type FieldDef, type FieldsDoc } from './api';

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
  let defaultId = $state('issue-tracker');
  let source = $state<'project' | string>('project');
  let draft = $state<FieldDef[]>([]);
  let version = $state(1);
  let extra = $state<Record<string, unknown>>({});
  let busy = $state(false);
  let error = $state('');
  let saveAsOpen = $state(false);
  let saveAsId = $state('');
  let saveAsName = $state('');
  let saveAsDefault = $state(true);
  let saveAsLayout = $state(true);

  let editingProject = $derived(source === 'project');
  let currentMeta = $derived(templates.find((t) => t.id === source));
  let canSave = $derived(editingProject || Boolean(currentMeta?.editable));

  async function loadList() {
    const body = await api.templates();
    templates = body.templates;
    defaultId = body.default;
  }

  async function loadFields() {
    error = '';
    try {
      const doc = editingProject
        ? await api.fields(projectSlug)
        : await api.templateFields(String(source));
      draft = (doc.fields || []).map((f) => ({ ...f, options: f.options ? [...f.options] : f.options }));
      version = doc.version ?? 1;
      extra = { ...doc };
      delete extra.fields;
      delete extra.version;
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

  function move(i: number, dir: number) {
    const j = i + dir;
    if (j < 0 || j >= draft.length) return;
    const next = [...draft];
    const ao = next[i].order;
    next[i] = { ...next[i], order: next[j].order };
    next[j] = { ...next[j], order: ao };
    [next[i], next[j]] = [next[j], next[i]];
    draft = next;
  }

  function addField() {
    const rows = draft.map((f) => parseInt(String(f.order), 10)).filter((n) => Number.isFinite(n));
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

  function removeField(i: number) {
    const id = draft[i]?.id;
    if (!id || RESERVED.has(id)) return;
    draft = draft.filter((_, idx) => idx !== i);
  }

  function setType(i: number, type: string) {
    const f = { ...draft[i], type };
    if ((type === 'select' || type === 'multiselect') && !f.options?.length) f.options = ['Option 1'];
    draft[i] = f;
    draft = draft;
  }

  function setOptions(i: number, text: string) {
    const options = text
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    draft[i] = { ...draft[i], options };
    draft = draft;
  }

  function payload(): FieldsDoc {
    return { version, fields: draft, ...extra } as FieldsDoc;
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
      defaultId = body.default;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Could not set default';
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="template-editor" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
  <div class="board-editor-title">Templates</div>
  <p class="template-help">
    Edit fields for this project, or save them as a starting point for new projects.
  </p>

  <div class="template-source">
    <button type="button" class:current={editingProject} onclick={() => (source = 'project')}>
      This project
    </button>
    {#each templates as t (t.id)}
      <button type="button" class:current={source === t.id} onclick={() => (source = t.id)}>
        {t.name}{t.is_default ? ' · default' : ''}{t.origin === 'shipped' ? ' · shipped' : ''}
      </button>
    {/each}
  </div>

  {#if error}
    <div class="empty-hint" style="color:var(--danger)">{error}</div>
  {/if}

  {#if !editingProject && currentMeta && !currentMeta.editable}
    <div class="empty-hint">Shipped templates are read-only. Save as Template to make an editable copy.</div>
  {/if}

  <div class="template-fields">
    {#each draft as f, i (f.id)}
      <div class="template-field">
        <div class="template-field-top">
          <button type="button" class="ghost" disabled={i === 0} onclick={() => move(i, -1)} title="Move up">↑</button>
          <button type="button" class="ghost" disabled={i === draft.length - 1} onclick={() => move(i, 1)} title="Move down">↓</button>
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
            onchange={(e) => setType(i, e.currentTarget.value)}
          >
            {#each CONTROL_TYPES as t}
              <option value={t}>{t}</option>
            {/each}
          </select>
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
            <button type="button" class="ghost" disabled={!canSave} onclick={() => removeField(i)}>Remove</button>
          {/if}
        </div>
        {#if f.type === 'select' || f.type === 'multiselect'}
          <textarea
            rows="3"
            disabled={!canSave}
            value={(f.options || []).join('\n')}
            oninput={(e) => setOptions(i, e.currentTarget.value)}
            placeholder="One option per line"
          ></textarea>
        {/if}
      </div>
    {/each}
  </div>

  <div class="board-editor-actions">
    <button type="button" class="ghost" disabled={!canSave} onclick={addField}>Add field</button>
    <span class="board-editor-actions-spacer"></span>
    <button type="button" class="ghost" onclick={onclose}>Close</button>
    {#if editingProject}
      <button type="button" onclick={openSaveAs}>Save as Template…</button>
    {/if}
    {#if !editingProject && currentMeta}
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
