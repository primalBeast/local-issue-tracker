<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { Editor } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Placeholder from '@tiptap/extension-placeholder';
  import Underline from '@tiptap/extension-underline';
  import Strike from '@tiptap/extension-strike';

  interface Props {
    value?: unknown;
    onchange?: (json: unknown) => void;
    placeholder?: string;
  }

  let { value = { type: 'doc', content: [] }, onchange, placeholder = 'Write notes…' }: Props = $props();

  let el: HTMLDivElement;
  let editor = $state<Editor | null>(null);
  let toolbarTick = $state(0);
  let showHelp = $state(false);

  let lastEmitted = '';

  const StrikeWithShortcuts = Strike.extend({
    addKeyboardShortcuts() {
      return {
        'Mod-Shift-s': () => this.editor.commands.toggleStrike(),
        'Mod-Shift-S': () => this.editor.commands.toggleStrike(),
        'Mod-Shift-x': () => this.editor.commands.toggleStrike(),
        'Mod-Shift-X': () => this.editor.commands.toggleStrike(),
      };
    },
  });

  function serialize(doc: unknown): string {
    try {
      return JSON.stringify(doc ?? { type: 'doc', content: [] });
    } catch {
      return '';
    }
  }

  onMount(() => {
    const initial = (value as object) || { type: 'doc', content: [] };
    lastEmitted = serialize(initial);

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
    editor = ed;
    lastEmitted = serialize(ed.getJSON());
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
</script>

<div class="rte-wrap">
  {#if editor}
    <div class="rte-toolbar" role="toolbar" aria-label="Text formatting">
      <button type="button" class="rte-btn" class:active={isActive('bold')} title="Bold (⌘B / Ctrl+B)" onclick={() => run(() => editor!.chain().focus().toggleBold().run())}>
        <strong>B</strong>
      </button>
      <button type="button" class="rte-btn" class:active={isActive('italic')} title="Italic (⌘I / Ctrl+I)" onclick={() => run(() => editor!.chain().focus().toggleItalic().run())}>
        <em>I</em>
      </button>
      <button type="button" class="rte-btn" class:active={isActive('underline')} title="Underline (⌘U / Ctrl+U)" onclick={() => run(() => editor!.chain().focus().toggleUnderline().run())}>
        <span class="u">U</span>
      </button>
      <button type="button" class="rte-btn" class:active={isActive('strike')} title="Strikethrough (⌘⇧X or ⌘⇧S)" onclick={() => run(() => editor!.chain().focus().toggleStrike().run())}>
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
            <tr><td>Bold</td><td><kbd>⌘B</kbd> / <kbd>Ctrl+B</kbd></td></tr>
            <tr><td>Italic</td><td><kbd>⌘I</kbd> / <kbd>Ctrl+I</kbd></td></tr>
            <tr><td>Underline</td><td><kbd>⌘U</kbd> / <kbd>Ctrl+U</kbd></td></tr>
            <tr><td>Strikethrough</td><td><kbd>⌘⇧X</kbd> or <kbd>⌘⇧S</kbd><br /><kbd>Ctrl+Shift+X</kbd> or <kbd>Ctrl+Shift+S</kbd></td></tr>
            <tr><td>Inline code</td><td><kbd>⌘E</kbd> / <kbd>Ctrl+E</kbd></td></tr>
            <tr><td>Bullet list</td><td><kbd>⌘⇧8</kbd> / <kbd>Ctrl+Shift+8</kbd></td></tr>
            <tr><td>Numbered list</td><td><kbd>⌘⇧7</kbd> / <kbd>Ctrl+Shift+7</kbd></td></tr>
            <tr><td>Blockquote</td><td><kbd>⌘⇧B</kbd> / <kbd>Ctrl+Shift+B</kbd></td></tr>
            <tr><td>Hard line break</td><td><kbd>⇧Enter</kbd> / <kbd>⌘Enter</kbd></td></tr>
            <tr><td>Undo</td><td><kbd>⌘Z</kbd> / <kbd>Ctrl+Z</kbd></td></tr>
            <tr><td>Redo</td><td><kbd>⌘⇧Z</kbd> / <kbd>Ctrl+Shift+Z</kbd></td></tr>
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
    background: #0e1219;
    overflow: hidden;
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
    background: rgba(110, 168, 254, 0.15);
    border-color: rgba(110, 168, 254, 0.4);
    color: var(--text, #e8eaed);
  }
  .rte-btn .u { text-decoration: underline; font-weight: 600; }
  .rte-btn .s { text-decoration: line-through; }
  .rte-help { margin-left: auto; font-weight: 650; }
  .rte-help-panel {
    padding: 8px 10px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(0, 0, 0, 0.2);
    font-size: 11.5px;
    color: var(--text-muted, #9aa3b2);
  }
  .rte-help-title { font-weight: 650; color: var(--text, #e8eaed); margin-bottom: 6px; }
  .rte-help-table { width: 100%; border-collapse: collapse; }
  .rte-help-table td { padding: 3px 0; vertical-align: top; }
  .rte-help-table td:first-child { width: 38%; color: var(--text, #e8eaed); }
  .rte-help-table kbd {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 4px;
    border: 1px solid var(--border, #2a3140);
    background: #12151c;
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 10.5px;
    color: var(--text, #e8eaed);
  }
  .rte-help-table code {
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 10.5px;
    color: #7dd3fc;
  }
  .rte { min-height: 100px; }
  .rte :global(.ProseMirror) {
    min-height: 100px;
    outline: none;
    padding: 8px;
    border: none;
    background: transparent;
    border-radius: 0;
  }
  .rte :global(.ProseMirror u),
  .rte :global(.ProseMirror [style*='underline']) { text-decoration: underline; }
  .rte :global(.ProseMirror s),
  .rte :global(.ProseMirror del),
  .rte :global(.ProseMirror strike) { text-decoration: line-through; }
</style>
