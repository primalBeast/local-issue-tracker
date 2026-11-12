import { describe, expect, it } from 'vitest';
import {
  DISCARD_LABEL,
  DISCARD_PROMPT,
  KEEP_LABEL,
  decideClose,
  idleGuard,
  promptCopy,
  requestClose,
  requestSwitch,
  resolvePrompt,
  type CloseReason,
} from './templateCloseGuard';

const reasons: CloseReason[] = ['escape', 'backdrop', 'x-button', 'close-button'];

describe('template close guard', () => {
  it('closes immediately when clean for Esc, backdrop, ✕, and Close', () => {
    for (const _reason of reasons) {
      expect(decideClose(false)).toBe('close');
      const result = requestClose(idleGuard(), false);
      expect(result.close).toBe(true);
      expect(result.state.prompt).toBe('none');
    }
  });

  it('prompts Discard unsaved changes? when dirty for Esc, backdrop, ✕, and Close', () => {
    for (const _reason of reasons) {
      expect(decideClose(true)).toBe('prompt');
      const result = requestClose(idleGuard(), true);
      expect(result.close).toBe(false);
      expect(result.state.prompt).toBe('close');
      expect(promptCopy(result.state)).toEqual({
        title: DISCARD_PROMPT,
        discard: DISCARD_LABEL,
        keep: KEEP_LABEL,
      });
      expect(DISCARD_PROMPT).toBe('Discard unsaved changes?');
    }
  });

  it('Discard closes and Keep editing stays', () => {
    const prompted = requestClose(idleGuard(), true).state;
    expect(resolvePrompt(prompted, 'keep')).toEqual({ state: idleGuard(), close: false, switchTo: null });
    expect(resolvePrompt(prompted, 'discard')).toEqual({ state: idleGuard(), close: true, switchTo: null });
  });

  it('switching templates while dirty asks, then discard switches', () => {
    const asked = requestSwitch(idleGuard(), true, 'other', 'project');
    expect(asked.switchTo).toBeNull();
    expect(asked.state.prompt).toBe('switch');
    expect(promptCopy(asked.state)?.title).toBe('Discard unsaved changes?');
    const discarded = resolvePrompt(asked.state, 'discard');
    expect(discarded.close).toBe(false);
    expect(discarded.switchTo).toBe('other');
    const kept = resolvePrompt(asked.state, 'keep');
    expect(kept.switchTo).toBeNull();
    expect(requestSwitch(idleGuard(), false, 'other', 'project').switchTo).toBe('other');
  });
});
