import { describe, expect, it } from 'vitest';
import { lastNoteLines, notesFieldText, tiptapToText } from './notePreview';

function para(text?: string) {
  if (text == null) return { type: 'paragraph' };
  return { type: 'paragraph', content: [{ type: 'text', text }] };
}

describe('lastNoteLines', () => {
  it('returns empty when there is no text', () => {
    expect(lastNoteLines('')).toEqual([]);
    expect(lastNoteLines('   \n\n')).toEqual([]);
  });

  it('drops blank lines at the end and keeps internal blanks', () => {
    expect(lastNoteLines('a\n\nb\n\n\n')).toEqual(['a', '', 'b']);
    expect(lastNoteLines('a\n  \n')).toEqual(['a']);
  });

  it('returns the last six lines of a longer note', () => {
    const lines = ['1', '2', '3', '4', '5', '6', '7', '8'];
    expect(lastNoteLines(lines.join('\n'))).toEqual(['3', '4', '5', '6', '7', '8']);
  });

  it('returns every line when there are fewer than six', () => {
    expect(lastNoteLines('only\ntwo')).toEqual(['only', 'two']);
  });

  it('normalizes Windows line endings', () => {
    expect(lastNoteLines('a\r\nb\r\n\r\n')).toEqual(['a', 'b']);
  });
});

describe('tiptapToText', () => {
  it('turns each paragraph into a line and keeps empty paragraphs', () => {
    const doc = {
      type: 'doc',
      content: [para('hello'), para(), para('world'), para(), para()],
    };
    expect(tiptapToText(doc)).toBe('hello\n\nworld\n\n');
    expect(lastNoteLines(tiptapToText(doc))).toEqual(['hello', '', 'world']);
  });

  it('treats hard breaks as extra lines inside a paragraph', () => {
    const doc = {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'first' },
            { type: 'hardBreak' },
            { type: 'text', text: 'second' },
          ],
        },
      ],
    };
    expect(tiptapToText(doc)).toBe('first\nsecond');
  });

  it('flattens list items to one line each', () => {
    const doc = {
      type: 'doc',
      content: [
        {
          type: 'bulletList',
          content: [
            { type: 'listItem', content: [para('one')] },
            { type: 'listItem', content: [para('two')] },
          ],
        },
      ],
    };
    expect(tiptapToText(doc)).toBe('one\ntwo');
  });
});

describe('notesFieldText', () => {
  it('accepts a plain string or TipTap JSON', () => {
    expect(notesFieldText(null)).toBe('');
    expect(notesFieldText('plain\nnote')).toBe('plain\nnote');
    expect(notesFieldText({ type: 'doc', content: [para('json')] })).toBe('json');
  });
});
