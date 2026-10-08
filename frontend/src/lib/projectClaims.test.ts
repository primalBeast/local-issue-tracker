import { describe, expect, it, vi } from 'vitest';
import { createProjectClaims, TAKEN_TITLE, type ClaimsStream, type ClaimOutcome } from './projectClaims';

class FakeStream implements ClaimsStream {
  static latest: FakeStream | null = null;
  readonly url: string;
  closed = false;
  private listeners = new Map<string, Array<(ev: { data?: string }) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeStream.latest = this;
  }

  addEventListener(type: string, listener: (ev: { data?: string }) => void): void {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  emit(type: string, data?: string): void {
    for (const listener of this.listeners.get(type) ?? []) listener({ data });
  }

  close(): void {
    this.closed = true;
  }
}

function claimsEvent(claims: Record<string, string>): string {
  return JSON.stringify({ claims });
}

describe('project claims', () => {
  it('disables a project another client holds, then enables it when the claim is released', () => {
    const interval = vi.spyOn(globalThis, 'setInterval');
    const timeout = vi.spyOn(globalThis, 'setTimeout');
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    try {
      const claimProject = vi.fn(async (): Promise<ClaimOutcome> => ({ ok: true }));
      const onLost = vi.fn();
      const seen: Array<Record<string, string>> = [];
      const claims = createProjectClaims({
        openEventSource: (url) => new FakeStream(url),
        claimProject,
        onLost,
      });
      claims.subscribe((next) => {
        seen.push(next);
      });
      claims.connect('client-a');

      const stream = FakeStream.latest;
      expect(stream?.url).toBe('/api/session/events?client=client-a');
      stream?.emit('open');
      stream?.emit('claims', claimsEvent({ alpha: 'client-b', beta: 'client-a' }));

      expect(claims.takenByOther('alpha')).toBe(true);
      expect(claims.takenByOther('beta')).toBe(false);
      expect(claims.pickerItemState('alpha', null)).toEqual({
        disabled: true,
        title: TAKEN_TITLE,
      });
      expect(TAKEN_TITLE).toBe('Already open in another window');
      expect(claims.pickerItemState('beta', 'beta')).toEqual({
        disabled: false,
        title: undefined,
      });
      expect(claims.pickerItemState('gamma', 'beta')).toEqual({
        disabled: false,
        title: undefined,
      });
      // The project this window has open stays disabled when someone else holds it.
      expect(claims.pickerItemState('alpha', 'alpha')).toEqual({
        disabled: true,
        title: TAKEN_TITLE,
      });

      stream?.emit('claims', claimsEvent({ beta: 'client-a' }));
      expect(claims.pickerItemState('alpha', null)).toEqual({
        disabled: false,
        title: undefined,
      });
      expect(seen.at(-1)).toEqual({ beta: 'client-a' });
      expect(claimProject).not.toHaveBeenCalled();
      expect(fetchMock).not.toHaveBeenCalled();
      expect(interval).not.toHaveBeenCalled();
      expect(timeout).not.toHaveBeenCalled();
    } finally {
      interval.mockRestore();
      timeout.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it('re-claims the current project after reconnect and calls onLost when another window holds it', async () => {
    let resolveClaim: (result: ClaimOutcome) => void = () => {};
    const claimProject = vi.fn(
      () =>
        new Promise<ClaimOutcome>((resolve) => {
          resolveClaim = resolve;
        })
    );
    const onLost = vi.fn();
    const claims = createProjectClaims({
      openEventSource: (url) => new FakeStream(url),
      claimProject,
      onLost,
    });
    claims.connect('client-a');
    claims.setCurrentProject('alpha');
    const stream = FakeStream.latest;
    expect(stream).not.toBeNull();

    stream?.emit('open');
    expect(claimProject).not.toHaveBeenCalled();

    stream?.emit('error');
    stream?.emit('open');
    expect(claimProject).toHaveBeenCalledTimes(1);
    expect(claimProject).toHaveBeenCalledWith('alpha');
    expect(onLost).not.toHaveBeenCalled();

    resolveClaim({ ok: false, heldByOther: true });
    await Promise.resolve();
    await Promise.resolve();
    expect(onLost).toHaveBeenCalledTimes(1);
    expect(onLost).toHaveBeenCalledWith('alpha');
  });

  it('keeps the project when the reconnect re-claim succeeds', async () => {
    const claimProject = vi.fn(async (): Promise<ClaimOutcome> => ({ ok: true }));
    const onLost = vi.fn();
    const claims = createProjectClaims({
      openEventSource: (url) => new FakeStream(url),
      claimProject,
      onLost,
    });
    claims.connect('client-a');
    claims.setCurrentProject('alpha');
    const stream = FakeStream.latest;
    stream?.emit('error');
    stream?.emit('open');
    await Promise.resolve();
    await Promise.resolve();
    expect(claimProject).toHaveBeenCalledWith('alpha');
    expect(onLost).not.toHaveBeenCalled();
  });
});
