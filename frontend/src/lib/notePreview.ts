/** Last N lines shown when hovering a ticket's open-dot in All Items. */
export const NOTE_PREVIEW_LINES = 6;

type TipTapNode = {
  type?: string;
  text?: string;
  content?: TipTapNode[];
};

function isNode(value: unknown): value is TipTapNode {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function inlineText(node: unknown): string {
  if (node == null) return '';
  if (typeof node === 'string') return node;
  if (Array.isArray(node)) return node.map(inlineText).join('');
  if (!isNode(node)) return '';
  if (node.type === 'text') return node.text || '';
  if (node.type === 'hardBreak') return '\n';
  return (node.content || []).map(inlineText).join('');
}

function renderBlocks(node: unknown): string[] {
  if (node == null) return [];
  if (typeof node === 'string') return node ? [node] : [];
  if (Array.isArray(node)) return node.flatMap(renderBlocks);
  if (!isNode(node)) return [];

  const type = node.type || '';
  const content = node.content || [];

  if (type === 'doc') return content.flatMap(renderBlocks);

  if (
    type === 'paragraph' ||
    type === 'heading' ||
    type === 'blockquote' ||
    type === 'codeBlock'
  ) {
    return [inlineText(node)];
  }

  if (type === 'bulletList' || type === 'orderedList') {
    return content.flatMap(renderBlocks);
  }

  if (type === 'listItem') {
    const parts: string[] = [];
    for (const child of content) {
      if (!isNode(child)) continue;
      if (child.type === 'bulletList' || child.type === 'orderedList') {
        parts.push(...renderBlocks(child));
        continue;
      }
      const text = inlineText(child);
      if (parts.length === 0) parts.push(text);
      else if (text) parts.push(text);
    }
    return parts.length ? parts : [''];
  }

  if (type === 'horizontalRule') return ['----'];
  if (content.length) return content.flatMap(renderBlocks);
  return [];
}

/** Plain text of a TipTap JSON document; each block is one line. */
export function tiptapToText(doc: unknown): string {
  return renderBlocks(doc).join('\n');
}

/** Notes field may be TipTap JSON or a plain string. */
export function notesFieldText(value: unknown): string {
  if (value == null || value === '') return '';
  if (typeof value === 'string') return value;
  return tiptapToText(value);
}

/**
 * Last `n` lines of notes, after dropping blank (whitespace-only) lines
 * at the end. Internal blank lines are kept.
 */
export function lastNoteLines(text: string, n = NOTE_PREVIEW_LINES): string[] {
  const lines = String(text ?? '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n');
  while (lines.length && lines[lines.length - 1].trim() === '') {
    lines.pop();
  }
  if (!lines.length) return [];
  const count = Math.max(0, n | 0);
  if (count === 0) return [];
  return lines.slice(-count);
}
