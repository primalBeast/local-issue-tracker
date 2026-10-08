import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createLayoutSaveGate, type LayoutSaveRequest } from './layoutSaveGate';

describe('layout save gate', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('coalesces edits into one debounced save', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.schedule();
    gate.schedule();
    await vi.advanceTimersByTimeAsync(399);
    expect(send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toEqual({ keepalive: false });
    expect(gate.busy()).toBe(false);
  });

  it('sends one layout save for a drag with many moves, on release', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    for (let i = 0; i < 20; i += 1) gate.schedule();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).not.toHaveBeenCalled();
    expect(gate.busy()).toBe(true);

    gate.release();
    expect(send).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).toHaveBeenCalledTimes(1);
    expect(gate.busy()).toBe(false);
  });

  it('sends a save requested while held when the hold is released', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    expect(send).not.toHaveBeenCalled();
    gate.schedule();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).not.toHaveBeenCalled();

    gate.release();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('flush during a hold sends the pending save and leaves the hold in place', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.schedule();
    const done = gate.flush({ keepalive: true });
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toEqual({ keepalive: true });
    await done;
    expect(gate.busy()).toBe(false);

    gate.schedule();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).toHaveBeenCalledTimes(1);

    gate.release();
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toEqual({ keepalive: false });
  });

  it('nested holds send once, on the outermost release', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.hold();
    gate.schedule();
    gate.release();
    expect(send).not.toHaveBeenCalled();
    gate.release();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('a click-sized release re-arms the debounce instead of sending immediately', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.schedule();
    gate.release({ debounce: true });
    expect(send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(400);
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('sends an oversized layout save immediately without keepalive', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.schedule({ large: true });
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toEqual({ keepalive: false });
    expect(gate.hasLargeSave()).toBe(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(gate.hasLargeSave()).toBe(false);

    gate.hold();
    gate.schedule({ large: true });
    expect(send).toHaveBeenCalledTimes(1);
    expect(gate.hasLargeSave()).toBe(true);
    const done = gate.flush({ keepalive: true });
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toEqual({ keepalive: false });
    await done;
  });

  it('resetHolds clears a leaked hold and saves once', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.schedule();
    gate.hold();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).not.toHaveBeenCalled();
    expect(gate.busy()).toBe(true);

    gate.resetHolds();
    expect(send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(399);
    expect(send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(send).toHaveBeenCalledTimes(1);

    // The pointerup that never came, arriving late, must not send again.
    gate.release();
    gate.release();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).toHaveBeenCalledTimes(1);

    gate.schedule();
    await vi.advanceTimersByTimeAsync(400);
    expect(send).toHaveBeenCalledTimes(2);
    expect(gate.busy()).toBe(false);
  });

  it('resetHolds with nothing pending does not save', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.resetHolds();
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).not.toHaveBeenCalled();
    expect(gate.busy()).toBe(false);
  });

  it('resetHolds does not restart a debounce that is already running', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.schedule();
    await vi.advanceTimersByTimeAsync(200);
    gate.resetHolds();
    await vi.advanceTimersByTimeAsync(200);
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('resetHolds sends a held oversized save immediately', async () => {
    const send = vi.fn(async (_req: LayoutSaveRequest) => {});
    const gate = createLayoutSaveGate({ delayMs: 400, send });

    gate.hold();
    gate.schedule({ large: true });
    expect(send).not.toHaveBeenCalled();
    gate.resetHolds();
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toEqual({ keepalive: false });
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).toHaveBeenCalledTimes(1);
  });
});
