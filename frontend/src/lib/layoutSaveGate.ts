/**
 * Debounced board-layout save with a drag hold.
 *
 * A panel drag schedules a save on pointer-down (z-index) and again on every
 * move. If that debounce fires mid-drag, the release schedules a second PUT.
 * hold() keeps the dirty flag and sends once on release(), like the item queue.
 * flush() still sends a save that is waiting on a hold (close / reload).
 * resetHolds() drops a leaked hold so a missed pointerup cannot block autosave.
 */

export type LayoutSaveRequest = {
  keepalive: boolean;
};

export type LayoutSaveGate = {
  /** Mark the layout dirty. While held, this does not start the debounce. */
  schedule(hint?: { large?: boolean }): void;
  /** A drag, resize, pan, or scrub is active. */
  hold(): void;
  /**
   * End one hold. The outermost release sends once.
   * `debounce` re-arms the timer instead (a click that did not move).
   */
  release(opts?: { debounce?: boolean }): void;
  /** Send a pending save now, including one held by a drag, and wait for it. */
  flush(opts?: { keepalive?: boolean }): Promise<void>;
  /**
   * Drop the hold count to 0. If a save is waiting, arm the debounce
   * (an oversized body sends immediately). A debounce that is already
   * running, with nothing held, is left alone.
   */
  resetHolds(): void;
  /** Drop a pending save. Does not cancel a PUT that has already started. */
  cancel(): void;
  /** True while a save is waiting or a PUT is still in flight. */
  busy(): boolean;
  /** True when a pending or in-flight save is over the keepalive budget. */
  hasLargeSave(): boolean;
};

type GateOptions = {
  delayMs?: number;
  send(req: LayoutSaveRequest): Promise<void>;
};

export function createLayoutSaveGate(opts: GateOptions): LayoutSaveGate {
  const delayMs = opts.delayMs ?? 400;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let held = 0;
  let dirty = false;
  let pendingLarge = false;
  let largeInflight = 0;
  let flight: Promise<void> | null = null;

  function clearTimer(): void {
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function arm(): void {
    if (held > 0 || !dirty) return;
    clearTimer();
    timer = setTimeout(() => {
      timer = null;
      if (held > 0 || !dirty) return;
      void startSend(false);
    }, delayMs);
  }

  function startSend(keepalive: boolean): Promise<void> {
    if (!dirty) return flight ?? Promise.resolve();
    const large = pendingLarge;
    pendingLarge = false;
    dirty = false;
    clearTimer();
    const useKeepalive = keepalive && !large;
    if (large) largeInflight += 1;
    let run: Promise<void>;
    try {
      run = Promise.resolve(opts.send({ keepalive: useKeepalive })).then(
        () => undefined,
        (err) => {
          console.error(err);
        }
      );
    } catch (err) {
      console.error(err);
      run = Promise.resolve();
    }
    if (large) {
      const trackedRun = run.finally(() => {
        largeInflight -= 1;
      });
      run = trackedRun;
    }
    const prev = flight;
    const tracked = (prev ? prev.then(() => run, () => run) : run).finally(() => {
      if (flight === tracked) flight = null;
    });
    flight = tracked;
    return tracked;
  }

  function schedule(hint?: { large?: boolean }): void {
    dirty = true;
    pendingLarge = !!hint?.large;
    clearTimer();
    if (held > 0) return;
    if (pendingLarge) {
      void startSend(false);
      return;
    }
    arm();
  }

  function hold(): void {
    held += 1;
    clearTimer();
  }

  function release(opts?: { debounce?: boolean }): void {
    if (held === 0) return;
    held -= 1;
    if (held > 0) return;
    if (!dirty) return;
    if (opts?.debounce) {
      arm();
      return;
    }
    void startSend(false);
  }

  async function flush(req?: { keepalive?: boolean }): Promise<void> {
    if (dirty) {
      await startSend(!!req?.keepalive);
      return;
    }
    if (flight) await flight;
  }

  function resetHolds(): void {
    const leaked = held > 0;
    held = 0;
    if (!dirty) return;
    if (!leaked && timer != null) return;
    if (pendingLarge) {
      void startSend(false);
      return;
    }
    arm();
  }

  function cancel(): void {
    dirty = false;
    pendingLarge = false;
    clearTimer();
  }

  function busy(): boolean {
    return dirty || timer != null || flight != null;
  }

  function hasLargeSave(): boolean {
    return pendingLarge || largeInflight > 0;
  }

  return {
    schedule,
    hold,
    release,
    flush,
    resetHolds,
    cancel,
    busy,
    hasLargeSave,
  };
}
