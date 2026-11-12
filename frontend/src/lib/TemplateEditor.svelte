<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { api, type FieldDef, type FieldsDoc } from './api';
  import ConfirmDiscard from './ConfirmDiscard.svelte';
  import FieldDetailsPanel from './FieldDetailsPanel.svelte';
  import TemplateLayoutCanvas from './TemplateLayoutCanvas.svelte';
  import TemplateList from './TemplateList.svelte';
  import TemplatePreview from './TemplatePreview.svelte';
  import {
    idleGuard,
    requestClose,
    requestSwitch,
    resolvePrompt,
    type CloseGuardState,
  } from './templateCloseGuard';
  import {
    editorIsDirty,
    extraFromDoc,
    normalizeLoadedFields,
    saveEnabled,
    savePayload,
    snapshotOf,
  } from './templateDirty';
  import {
    addField,
    patchField,
    removeField,
    sampleValue,
    setFieldOptions,
    setFieldType,
    slugify,
  } from './templateFields';
  import { handleFocusTrap, restoreFocus } from './templateFocusTrap';
  import { dialogTitle, type TemplateInfo, type TemplateSource } from './templateListModel';
  import {
    moveToAdjacentRow,
    moveToNewRow,
    moveWithinRow,
    setFieldWidth,
  } from './templatePlacement';
  import { nextSelectionAfterRemove } from './templateSelection';

  interface Props {
    projectSlug: string;
    projectName: string;
    onclose: () => void;
    onprojectfields: (doc: FieldsDoc) => void;
  }

  let { projectSlug, projectName, onclose, onprojectfields }: Props = $props();

  let templates = $state<TemplateInfo[]>([]);
  let source = $state<TemplateSource>('project');
  let draft = $state<FieldDef[]>([]);
  let version = $state(1);
  let extra = $state<Record<string, unknown>>({});
  let previewValues = $state<Record<string, unknown>>({});
  let snapshot = $state('');
  let selectedId = $state<string | null>(null);
  let busy = $state(false);
  let error = $state('');
  let saveAsOpen = $state(false);
  let saveAsId = $state('');
  let saveAsName = $state('');
  let saveAsDefault = $state(true);
  let saveAsLayout = $state(true);
  let guard = $state<CloseGuardState>(idleGuard());
  let dialogEl = $state<HTMLDivElement | null>(null);
  let opener: Element | null = null;

  let editingProject = $derived(source === 'project');
  let currentMeta = $derived(templates.find((t) => t.id === source));
  let canSave = $derived(editingProject || Boolean(currentMeta?.editable));
  let title = $derived(dialogTitle(source, templates, projectName));
  let dirty = $derived(Boolean(snapshot) && editorIsDirty(draft, extra, version, snapshot));
  let selected = $derived(draft.find((f) => f.id === selectedId) ?? null);
  let saveOk = $derived(saveEnabled(canSave, dirty, busy));

  async function loadList() {
    const body = await api.templates();
    templates = body.templates;
  }

  async function loadFields() {
    error = '';
    try {
      const doc = editingProject ? await api.fields(projectSlug) : await api.templateFields(String(source));
      const fields = normalizeLoadedFields(doc.fields || []);
      draft = fields;
      version = doc.version ?? 1;
      extra = extraFromDoc(doc);
      snapshot = snapshotOf(draft, extra, version);
      previewValues = Object.fromEntries(fields.map((f) => [f.id, sampleValue(f)]));
      selectedId = fields.some((f) => f.id === selectedId) ? selectedId : (fields[0]?.id ?? null);
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

  function setDraft(next: FieldDef[]) {
    draft = next;
  }

  function onSelectSource(next: TemplateSource) {
    const result = requestSwitch(guard, dirty, next, source);
    guard = result.state;
    if (result.switchTo != null) source = result.switchTo;
  }

  function askClose() {
    const result = requestClose(guard, dirty);
    guard = result.state;
    if (result.close) finishClose();
  }

  function finishClose() {
    restoreFocus(opener);
    onclose();
  }

  function onPrompt(choice: 'discard' | 'keep') {
    const result = resolvePrompt(guard, choice);
    guard = result.state;
    if (result.switchTo != null) source = result.switchTo;
    if (result.close) finishClose();
  }

  function onBackdrop(e: MouseEvent) {
    if (e.target !== e.currentTarget) return;
    askClose();
  }

  function onDialogKey(e: KeyboardEvent) {
    if (guard.prompt !== 'none') return;
    if (e.key === 'Tab' && dialogEl) handleFocusTrap(dialogEl, e);
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      askClose();
    }
  }

  function onMove(id: string, action: 'earlier' | 'later' | 'prev-row' | 'next-row' | 'new-row') {
    if (action === 'earlier') setDraft(moveWithinRow(draft, id, -1));
    else if (action === 'later') setDraft(moveWithinRow(draft, id, 1));
    else if (action === 'prev-row') setDraft(moveToAdjacentRow(draft, id, -1));
    else if (action === 'next-row') setDraft(moveToAdjacentRow(draft, id, 1));
    else setDraft(moveToNewRow(draft, id));
  }

  function onRemove(id: string) {
    selectedId = nextSelectionAfterRemove(draft, id, selectedId);
    setDraft(removeField(draft, id));
  }

  function onAdd() {
    const next = addField(draft);
    draft = next;
    selectedId = next[next.length - 1]?.id ?? selectedId;
  }

  async function save() {
    if (!saveOk) return;
    busy = true;
    error = '';
    try {
      const doc = savePayload(draft, extra, version);
      if (editingProject) {
        const saved = await api.putFields(projectSlug, doc);
        onprojectfields(saved);
      } else {
        await api.putTemplateFields(String(source), doc);
      }
      snapshot = snapshotOf(draft, extra, version);
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

  let windowKey: ((e: KeyboardEvent) => void) | null = null;

  onMount(() => {
    opener = document.activeElement;
    windowKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (guard.prompt !== 'none') return;
      e.preventDefault();
      e.stopPropagation();
      if (saveAsOpen) {
        saveAsOpen = false;
        return;
      }
      askClose();
    };
    window.addEventListener('keydown', windowKey, true);
    void tick().then(() => dialogEl?.focus());
  });

  onDestroy(() => {
    if (windowKey) window.removeEventListener('keydown', windowKey, true);
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="confirm-backdrop template-editor-backdrop" role="presentation" onclick={onBackdrop}>
  <div
    class="template-editor"
    bind:this={dialogEl}
    role="dialog"
    aria-modal="true"
    aria-labelledby="template-editor-title"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    onkeydown={onDialogKey}
  >
    <div class="template-editor-head">
      <div class="board-editor-title" id="template-editor-title">
        {title}
        {#if dirty}
          <span class="unsaved-dot" title="Unsaved changes" aria-label="Unsaved changes">•</span>
        {/if}
      </div>
      <button type="button" class="ghost theme-dialog-close" aria-label="Close" onclick={askClose}>✕</button>
    </div>

    {#if error}
      <div class="empty-hint" style="color:var(--danger)">{error}</div>
    {/if}

    {#if !editingProject && currentMeta && !currentMeta.editable}
      <div class="empty-hint">Built-in (read-only). Save as copy to make an editable copy.</div>
    {/if}

    <div class="template-editor-body">
      <TemplateList {templates} {source} onselect={onSelectSource} onsetdefault={makeDefault} />
      <div class="template-editor-main">
        <TemplateLayoutCanvas
          fields={draft}
          {selectedId}
          disabled={!canSave}
          onfields={setDraft}
          onselect={(id) => (selectedId = id)}
          onadd={onAdd}
        />
        <div class="template-editor-stage">
          <FieldDetailsPanel
            field={selected}
            fields={draft}
            disabled={!canSave}
            onpatch={(id, patch) => setDraft(patchField(draft, id, patch))}
            onsettype={(id, type) => setDraft(setFieldType(draft, id, type))}
            onsetoptions={(id, text) => setDraft(setFieldOptions(draft, id, text))}
            onsetwidth={(id, width) => setDraft(setFieldWidth(draft, id, width))}
            onmove={onMove}
            onremove={onRemove}
          />
          <TemplatePreview
            {draft}
            {previewValues}
            {selectedId}
            onselect={(id) => (selectedId = id)}
            onpreview={patchPreview}
          />
        </div>
      </div>
    </div>

    <div class="board-editor-actions template-editor-footer">
      <button type="button" class="ghost" onclick={askClose}>Close</button>
      <span class="board-editor-actions-spacer"></span>
      <button type="button" onclick={openSaveAs}>Save as copy…</button>
      <button type="button" class="primary" disabled={!saveOk} onclick={() => void save()}>Save</button>
    </div>

    {#if saveAsOpen}
      <div class="template-saveas">
        <div class="project-section-title">Save as copy</div>
        <label class="field-label" for="tpl-id">Id</label>
        <input id="tpl-id" type="text" bind:value={saveAsId} placeholder="issue-tracker" />
        <label class="field-label" for="tpl-name" style="margin-top:8px">Name</label>
        <input id="tpl-name" type="text" bind:value={saveAsName} />
        <label class="check-row" style="margin-top:8px">
          <input type="checkbox" bind:checked={saveAsDefault} />
          Default for new projects
        </label>
        <label class="check-row">
          <input type="checkbox" bind:checked={saveAsLayout} />
          Include Main Board layout (no tickets)
        </label>
        <div class="board-editor-actions">
          <button type="button" class="ghost" onclick={() => (saveAsOpen = false)}>Cancel</button>
          <button type="button" class="primary" disabled={busy || !saveAsId.trim()} onclick={() => void confirmSaveAs()}>
            Save copy
          </button>
        </div>
      </div>
    {/if}
  </div>
</div>

{#if guard.prompt !== 'none'}
  <ConfirmDiscard ondiscard={() => onPrompt('discard')} onkeep={() => onPrompt('keep')} />
{/if}
