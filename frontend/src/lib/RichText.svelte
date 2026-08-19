<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import type { Editor } from '@tiptap/core';
  import { formatNoteDateStamp } from './noteDate';

  interface Props {
    value?: unknown;
    onchange?: (json: unknown) => void;
    placeholder?: string;
    fill?: boolean;
  }

  let {
    value = { type: 'doc', content: [] },
    onchange,
    placeholder = 'Write notes…',
    fill = false,
  }: Props = $props();

  let el: HTMLDivElement;
  let wrapEl = $state<HTMLDivElement | null>(null);
  let editor = $state<Editor | null>(null);
  let toolbarTick = $state(0);
  let showHelp = $state(false);
  const isMac =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  let editorError = $state<string | null>(null);

  /** Last JSON we emitted to parent — ignore echo updates. */
  let lastEmitted = '';

  function serialize(doc: unknown): string {
    try {
      return JSON.stringify(doc ?? { type: 'doc', content: [] });
    } catch {
      return '';
    }
  }

  onMount(() => {
    // Snapshot initial value once at mount. Parent must remount (via {#key}) to load different content.
    // NO $effect syncing value ↔ editor — that caused effect_update_depth_exceeded and froze the app.
    const initial = (value as object) || { type: 'doc', content: [] };
    lastEmitted = serialize(initial);
    let cancelled = false;

    // Dynamic import so the rest of the UI can load even if TipTap chunks 404.
    void (async () => {
      try {
        const [{ Editor }, { default: StarterKit }, { default: Placeholder }, { default: Underline }, { default: Strike }] =
          await Promise.all([
            import('@tiptap/core'),
            import('@tiptap/starter-kit'),
            import('@tiptap/extension-placeholder'),
            import('@tiptap/extension-underline'),
            import('@tiptap/extension-strike'),
          ]);
        if (cancelled) return;

        const StrikeWithShortcuts = Strike.extend({
          addKeyboardShortcuts() {
            return {
              'Ctrl-q': () => this.editor.commands.toggleStrike(),
              'Ctrl-Q': () => this.editor.commands.toggleStrike(),
              'Mod-;': () => this.editor.commands.insertContent(formatNoteDateStamp()),
            };
          },
        });

        const ed = new Editor({
          element: el,
          extensions: [
            StarterKit.configure({
              strike: false,
            }),
            Underline,
            StrikeWithShortcuts,
            Placeholder.configure({ placeholder }),
          ],
          content: initial,
          onUpdate: ({ editor: instance }) => {
            const json = instance.getJSON();
            const s = serialize(json);
            if (s === lastEmitted) return;
            lastEmitted = s;
            onchange?.(json);
          },
          onSelectionUpdate: () => {
            toolbarTick += 1;
          },
        });
        if (cancelled) {
          ed.destroy();
          return;
        }
        editor = ed;
        // TipTap may normalize initial doc; treat that as baseline (do not emit)
        lastEmitted = serialize(ed.getJSON());
        requestAnimationFrame(() => {
          requestAnimationFrame(() => scrollNotesToEnd());
        });
      } catch (e) {
        if (!cancelled) {
          editorError = e instanceof Error ? e.message : String(e);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  });

  onDestroy(() => {
    editor?.destroy();
    editor = null;
  });

  function run(cmd: () => void) {
    if (!editor) return;
    cmd();
    toolbarTick += 1;
  }

  function isActive(name: string): boolean {
    void toolbarTick;
    return editor?.isActive(name) ?? false;
  }

  function scrollNotesToEnd() {
    const wrap = wrapEl;
    if (!wrap) return;
    const rte = wrap.querySelector('.rte') as HTMLElement | null;
    const pm = wrap.querySelector('.ProseMirror') as HTMLElement | null;
    const body = wrap.closest('.panel-body') as HTMLElement | null;
    for (const node of [rte, pm, body]) {
      if (node) node.scrollTop = node.scrollHeight;
    }
  }

  function isStrikeHotkey(e: KeyboardEvent): boolean {
    if (!e.ctrlKey || e.metaKey || e.altKey) return false;
    return e.code === 'KeyQ' || e.key === 'q' || e.key === 'Q';
  }

  function isDateHotkey(e: KeyboardEvent): boolean {
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return false;
    return e.code === 'Semicolon' || e.key === ';';
  }

  function onNotesHotkey(e: KeyboardEvent) {
    if (isStrikeHotkey(e)) {
      e.preventDefault();
      e.stopPropagation();
      if (!editor) return;
      editor.chain().focus().toggleStrike().run();
      toolbarTick += 1;
      return;
    }
    if (isDateHotkey(e)) {
      e.preventDefault();
      e.stopPropagation();
      if (!editor) return;
      editor.chain().focus().insertContent(formatNoteDateStamp()).run();
      toolbarTick += 1;
    }
  }

  $effect(() => {
    const wrap = wrapEl;
    if (!wrap) return;
    wrap.addEventListener('keydown', onNotesHotkey, true);
    return () => wrap.removeEventListener('keydown', onNotesHotkey, true);
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="rte-wrap" class:fill role="group" aria-label="Notes editor" bind:this={wrapEl}>
  {#if editorError}
    <div class="empty-hint" style="padding:8px">Notes editor failed to load. The rest of the app still works.</div>
  {:else if !editor}
    <div class="empty-hint" style="padding:8px">Loading notes editor…</div>
  {/if}
  {#if editor}
    <div class="rte-toolbar" role="toolbar" aria-label="Text formatting">
      <button
        type="button"
        class="rte-btn"
        class:active={isActive('bold')}
        title={isMac ? 'Bold (⌘B)' : 'Bold (Ctrl+B)'}
        onclick={() => run(() => editor!.chain().focus().toggleBold().run())}
      >
        <strong>B</strong>
      </button>
      <button
        type="button"
        class="rte-btn"
        class:active={isActive('italic')}
        title={isMac ? 'Italic (⌘I)' : 'Italic (Ctrl+I)'}
        onclick={() => run(() => editor!.chain().focus().toggleItalic().run())}
      >
        <em>I</em>
      </button>
      <button
        type="button"
        class="rte-btn"
        class:active={isActive('underline')}
        title={isMac ? 'Underline (⌘U)' : 'Underline (Ctrl+U)'}
        onclick={() => run(() => editor!.chain().focus().toggleUnderline().run())}
      >
        <span class="u">U</span>
      </button>
      <button
        type="button"
        class="rte-btn"
        class:active={isActive('strike')}
        title="Strikethrough (Ctrl+Q)"
        onclick={() => run(() => editor!.chain().focus().toggleStrike().run())}
      >
        <span class="s">S</span>
      </button>
      <button
        type="button"
        class="rte-btn rte-help"
        class:active={showHelp}
        title="Show formatting shortcuts"
        onpointerdown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onclick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          showHelp = !showHelp;
        }}
      >
        ?
      </button>
    </div>
    {#if showHelp}
      <div class="rte-help-panel">
        <div class="rte-help-title">Formatting shortcuts</div>
        <table class="rte-help-table">
          <tbody>
            {#if isMac}
              <tr><td>Bold</td><td><kbd>⌘B</kbd></td></tr>
              <tr><td>Italic</td><td><kbd>⌘I</kbd></td></tr>
              <tr><td>Underline</td><td><kbd>⌘U</kbd></td></tr>
              <tr><td>Strikethrough</td><td><kbd>Ctrl+Q</kbd></td></tr>
              <tr><td>Insert date</td><td><kbd>⌘;</kbd> → <code>m/d - </code></td></tr>
              <tr><td>Inline code</td><td><kbd>⌘E</kbd></td></tr>
              <tr><td>Bullet list</td><td><kbd>⌘⇧8</kbd></td></tr>
              <tr><td>Numbered list</td><td><kbd>⌘⇧7</kbd></td></tr>
              <tr><td>Blockquote</td><td><kbd>⌘⇧B</kbd></td></tr>
              <tr><td>Hard line break</td><td><kbd>⇧Enter</kbd> / <kbd>⌘Enter</kbd></td></tr>
              <tr><td>Undo</td><td><kbd>⌘Z</kbd></td></tr>
              <tr><td>Redo</td><td><kbd>⌘⇧Z</kbd></td></tr>
            {:else}
              <tr><td>Bold</td><td><kbd>Ctrl+B</kbd></td></tr>
              <tr><td>Italic</td><td><kbd>Ctrl+I</kbd></td></tr>
              <tr><td>Underline</td><td><kbd>Ctrl+U</kbd></td></tr>
              <tr><td>Strikethrough</td><td><kbd>Ctrl+Q</kbd></td></tr>
              <tr><td>Insert date</td><td><kbd>Ctrl+;</kbd> → <code>m/d - </code></td></tr>
              <tr><td>Inline code</td><td><kbd>Ctrl+E</kbd></td></tr>
              <tr><td>Bullet list</td><td><kbd>Ctrl+Shift+8</kbd></td></tr>
              <tr><td>Numbered list</td><td><kbd>Ctrl+Shift+7</kbd></td></tr>
              <tr><td>Blockquote</td><td><kbd>Ctrl+Shift+B</kbd></td></tr>
              <tr><td>Hard line break</td><td><kbd>Shift+Enter</kbd></td></tr>
              <tr><td>Undo</td><td><kbd>Ctrl+Z</kbd></td></tr>
              <tr><td>Redo</td><td><kbd>Ctrl+Shift+Z</kbd></td></tr>
            {/if}
            <tr><td>Markdown-ish</td><td><code>**bold**</code> <code>*italic*</code> <code>~~strike~~</code></td></tr>
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
  <div class="rte" bind:this={el}></div>
</div>

<style>
  .rte-wrap {
    border: 1px solid var(--border, #2a3140);
    border-radius: 8px;
    background: var(--bg-input, #0e1219);
    overflow: hidden;
  }

  .rte-wrap.fill {
    flex: 1 1 auto;
    min-height: calc(1.4em * 3 + 16px);
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .rte-toolbar {
    display: flex;
    gap: 4px;
    padding: 4px 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(255, 255, 255, 0.02);
  }

  .rte-btn {
    min-width: 28px;
    height: 26px;
    padding: 0 6px;
    border-radius: 6px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted, #9aa3b2);
    font-size: 13px;
    line-height: 1;
  }

  .rte-btn:hover {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text, #e8eaed);
    border-color: var(--border, #2a3140);
  }

  .rte-btn.active {
    background: var(--accent-soft, rgba(110, 168, 254, 0.15));
    border-color: color-mix(in srgb, var(--accent, #6ea8fe) 40%, transparent);
    color: var(--text, #e8eaed);
  }

  .rte-btn .u {
    text-decoration: underline;
    font-weight: 600;
  }

  .rte-btn .s {
    text-decoration: line-through;
  }

  .rte-help {
    margin-left: auto;
    font-weight: 650;
  }

  .rte-help-panel {
    padding: 8px 10px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(0, 0, 0, 0.2);
    font-size: 11.5px;
    color: var(--text-muted, #9aa3b2);
  }

  .rte-help-title {
    font-weight: 650;
    color: var(--text, #e8eaed);
    margin-bottom: 6px;
  }

  .rte-help-table {
    width: 100%;
    border-collapse: collapse;
  }

  .rte-help-table td {
    padding: 3px 0;
    vertical-align: top;
  }

  .rte-help-table td:first-child {
    width: 38%;
    color: var(--text, #e8eaed);
  }

  .rte-help-table kbd {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 4px;
    border: 1px solid var(--border, #2a3140);
    background: var(--bg-elevated, #12151c);
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 10.5px;
    color: var(--text, #e8eaed);
  }

  .rte-help-table code {
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 10.5px;
    color: #7dd3fc;
  }

  .rte {
    min-height: calc(1.4em * 3 + 16px);
  }

  .rte-wrap.fill .rte {
    flex: 1 1 auto;
    min-height: calc(1.4em * 3 + 16px);
    overflow: auto;
  }

  .rte :global(.ProseMirror) {
    min-height: calc(1.4em * 3 + 16px);
    outline: none;
    padding: 8px;
    border: none;
    background: transparent;
    border-radius: 0;
    font-size: 16px;
    line-height: 1.45;
  }

  .rte-wrap.fill .rte :global(.ProseMirror) {
    min-height: 100%;
  }

  .rte :global(.ProseMirror u),
  .rte :global(.ProseMirror [style*='underline']) {
    text-decoration: underline;
  }

  .rte :global(.ProseMirror s),
  .rte :global(.ProseMirror del),
  .rte :global(.ProseMirror strike) {
    text-decoration: line-through;
  }
</style>
