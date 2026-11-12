import { describe, expect, it } from 'vitest';
import {
  fieldIdFromTarget,
  fieldIdFromTitleBarClick,
  isSelected,
  nextSelectionAfterRemove,
  previewScrollId,
  scrollCounterpartIntoView,
  selectField,
} from './templateSelection';

describe('preview selection', () => {
  it('selects the field whose preview hit was clicked', () => {
    expect(selectField(null, 'priority')).toBe('priority');
    expect(selectField('title', 'notes')).toBe('notes');
    expect(isSelected('notes', 'notes')).toBe(true);
    expect(isSelected('notes', 'title')).toBe(false);
  });

  it('reads data-field-id from the clicked preview node', () => {
    const root = { getAttribute: (n: string) => (n === 'data-field-id' ? 'urgency' : null) };
    const node = {
      closest: (sel: string) => (sel === '[data-field-id]' ? root : null),
    };
    expect(fieldIdFromTarget(node as unknown as EventTarget)).toBe('urgency');
    expect(fieldIdFromTarget(null)).toBeNull();
  });

  it('maps title-bar clicks onto ticket number, description, or alternate', () => {
    const labels = { ticket: 'Ticket number', title: 'Description', alternate: 'Alternate ticket' };
    const click = (text: string) => {
      const label = { textContent: text, trim() { return text; } };
      const wrap = { querySelector: () => label };
      const target = { closest: (sel: string) => (sel === 'label' ? wrap : null) };
      return fieldIdFromTitleBarClick(target as unknown as EventTarget, labels);
    };
    expect(click('Description')).toBe('title');
    expect(click('Alternate ticket')).toBe('alternate_ticket');
    expect(click('Ticket number')).toBe('ticket_key');
  });

  it('scrolls the counterpart into view, mapping title-bar fields onto one preview hit', () => {
    expect(previewScrollId('title')).toBe('ticket_key');
    expect(previewScrollId('alternate_ticket')).toBe('ticket_key');
    expect(previewScrollId('notes')).toBe('notes');

    const scrolled: string[] = [];
    const node = (fieldId: string) => ({
      dataset: { fieldId },
      scrollIntoView() {
        scrolled.push(fieldId);
      },
    });
    const chip = node('notes');
    const titleHit = node('ticket_key');
    const notesHit = node('notes');
    const root = {
      querySelectorAll(sel: string) {
        return sel === '.template-chip' ? [chip] : [titleHit, notesHit];
      },
    };
    scrollCounterpartIntoView(root as unknown as ParentNode, 'preview', 'notes');
    scrollCounterpartIntoView(root as unknown as ParentNode, 'canvas', 'title');
    expect(scrolled).toEqual(['notes', 'ticket_key']);
  });

  it('keeps a neighbor selected after remove', () => {
    const fields = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
    expect(nextSelectionAfterRemove(fields, 'b', 'b')).toBe('c');
    expect(nextSelectionAfterRemove(fields, 'c', 'c')).toBe('b');
    expect(nextSelectionAfterRemove(fields, 'b', 'a')).toBe('a');
  });
});
