export type CloseReason = 'escape' | 'backdrop' | 'x-button' | 'close-button';

export type GuardPrompt = 'none' | 'close' | 'switch';

export type CloseGuardState = {
  prompt: GuardPrompt;
  pendingSource: string | null;
};

export const DISCARD_PROMPT = 'Discard unsaved changes?';
export const DISCARD_LABEL = 'Discard';
export const KEEP_LABEL = 'Keep editing';

export function idleGuard(): CloseGuardState {
  return { prompt: 'none', pendingSource: null };
}

export function decideClose(dirty: boolean): 'close' | 'prompt' {
  return dirty ? 'prompt' : 'close';
}

export function requestClose(state: CloseGuardState, dirty: boolean): { state: CloseGuardState; close: boolean } {
  if (!dirty) return { state: idleGuard(), close: true };
  return { state: { prompt: 'close', pendingSource: null }, close: false };
}

export function requestSwitch(
  state: CloseGuardState,
  dirty: boolean,
  nextSource: string,
  currentSource: string
): { state: CloseGuardState; switchTo: string | null } {
  if (nextSource === currentSource) return { state, switchTo: null };
  if (!dirty) return { state: idleGuard(), switchTo: nextSource };
  return { state: { prompt: 'switch', pendingSource: nextSource }, switchTo: null };
}

export function resolvePrompt(
  state: CloseGuardState,
  choice: 'discard' | 'keep'
): { state: CloseGuardState; close: boolean; switchTo: string | null } {
  if (choice === 'keep') return { state: idleGuard(), close: false, switchTo: null };
  if (state.prompt === 'switch') {
    return { state: idleGuard(), close: false, switchTo: state.pendingSource };
  }
  if (state.prompt === 'close') {
    return { state: idleGuard(), close: true, switchTo: null };
  }
  return { state: idleGuard(), close: false, switchTo: null };
}

export function promptCopy(state: CloseGuardState): { title: string; discard: string; keep: string } | null {
  if (state.prompt === 'none') return null;
  return { title: DISCARD_PROMPT, discard: DISCARD_LABEL, keep: KEEP_LABEL };
}
