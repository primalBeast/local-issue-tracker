import type { Item } from './api';

/** One PATCH body plus the routing captured when the edit was scheduled. */
export type ItemSaveRequest = {
  slug: string;
  itemId: string;
  fields: Record<string, unknown>;
  version: number | undefined;
  keepalive: boolean;
};

export type ItemSaveQueue = {
  schedule(slug: string, itemId: string, fields: Record<string, unknown>): void;
  flush(): Promise<void>;
  flushKeepalive(): void;
  hold(): void;
  release(): void;
  cancel(itemId: string): void;
  hasPending(): boolean;
  /** True while a save is queued or a PATCH is still in flight. */
  busy(): boolean;
  /** Drop every queued edit without sending. In-flight PATCHes are left alone. */
  cancelAll(): void;
  /** Fields queued for `itemId` that have not been sent yet. */
  pendingFields(itemId: string): Record<string, unknown> | undefined;
};

type Slot = {
  slug: string;
  fields: Record<string, unknown>;
  timer: ReturnType<typeof setTimeout> | null;
  /** Bumped on every schedule so a waiter can see that the batch changed. */
  gen: number;
};

type QueueOptions = {
  delayMs?: number;
  send(req: ItemSaveRequest): Promise<Item>;
  getVersion(itemId: string): number | undefined;
  onSaved(itemId: string, item: Item, slug: string): void;
  onError(itemId: string, slug: string, err: unknown): void | Promise<void>;
};

export function createItemSaveQueue(opts: QueueOptions): ItemSaveQueue {
  const delayMs = opts.delayMs ?? 350;
  const slots = new Map<string, Slot>();
  /** Per item, resolves after that item's sends (and their onSaved/onError) settle. */
  const inflight = new Map<string, Promise<void>>();
  let held = false;

  function arm(itemId: string): void {
    const slot = slots.get(itemId);
    if (!slot || held) return;
    if (slot.timer != null) globalThis.clearTimeout(slot.timer);
    const gen = slot.gen;
    slot.timer = globalThis.setTimeout(() => {
      const current = slots.get(itemId);
      if (!current || current.gen !== gen) return;
      current.timer = null;
      void pump(itemId, gen);
    }, delayMs);
  }

  /**
   * Start the PATCH now. `send` is called synchronously so a keepalive flush
   * still reaches fetch while the page is unloading.
   */
  function startSend(itemId: string, keepalive: boolean): Promise<void> {
    const slot = slots.get(itemId);
    if (!slot) return Promise.resolve();
    slots.delete(itemId);
    if (slot.timer != null) {
      globalThis.clearTimeout(slot.timer);
      slot.timer = null;
    }
    const { slug, fields } = slot;
    // One version for the merged patch, read at send time so a response that
    // just landed can chain into the next request.
    const version = opts.getVersion(itemId);

    let resolveGate!: () => void;
    const gate = new Promise<void>((resolve) => {
      resolveGate = resolve;
    });
    const prev = inflight.get(itemId);
    const tracked = (prev ? prev.then(() => gate, () => gate) : gate).finally(() => {
      if (inflight.get(itemId) === tracked) inflight.delete(itemId);
    });
    inflight.set(itemId, tracked);

    const finish = (work: Promise<void>) => {
      void work.then(
        () => resolveGate(),
        (err) => {
          console.error(err);
          resolveGate();
        }
      );
    };

    try {
      const sent = opts.send({ slug, itemId, fields, version, keepalive });
      finish(
        Promise.resolve(sent).then(
          (saved) => {
            try {
              opts.onSaved(itemId, saved, slug);
            } catch (err) {
              console.error(err);
            }
          },
          async (err: unknown) => {
            try {
              await opts.onError(itemId, slug, err);
            } catch (handlerErr) {
              console.error(handlerErr);
            }
          }
        )
      );
    } catch (err) {
      finish(
        Promise.resolve()
          .then(() => opts.onError(itemId, slug, err))
          .then(
            () => undefined,
            (handlerErr) => {
              console.error(handlerErr);
            }
          )
      );
    }

    return tracked;
  }

  /** Debounce elapsed. Wait out an in-flight PATCH, then send the merged batch. */
  async function pump(itemId: string, gen: number): Promise<void> {
    for (;;) {
      const flight = inflight.get(itemId);
      if (!flight) break;
      await flight;
      const slot = slots.get(itemId);
      if (!slot || slot.gen !== gen) return;
    }
    if (held) return;
    const slot = slots.get(itemId);
    if (!slot || slot.gen !== gen || slot.timer != null) return;
    startSend(itemId, false);
  }

  function schedule(slug: string, itemId: string, fields: Record<string, unknown>): void {
    let slot = slots.get(itemId);
    if (!slot) {
      slot = { slug, fields: {}, timer: null, gen: 0 };
      slots.set(itemId, slot);
    }
    slot.slug = slug;
    slot.fields = { ...slot.fields, ...fields };
    slot.gen += 1;
    if (slot.timer != null) {
      globalThis.clearTimeout(slot.timer);
      slot.timer = null;
    }
    if (held) return;
    arm(itemId);
  }

  async function flush(): Promise<void> {
    for (let guard = 0; guard < 100; guard += 1) {
      for (const itemId of [...slots.keys()]) {
        const slot = slots.get(itemId);
        if (!slot) continue;
        if (slot.timer != null) {
          globalThis.clearTimeout(slot.timer);
          slot.timer = null;
        }
        if (!inflight.has(itemId)) startSend(itemId, false);
      }
      if (inflight.size === 0) return;
      await Promise.all([...inflight.values()]);
      if (slots.size === 0 && inflight.size === 0) return;
    }
  }

  function flushKeepalive(): void {
    for (const itemId of [...slots.keys()]) startSend(itemId, true);
  }

  function hold(): void {
    held = true;
    for (const slot of slots.values()) {
      if (slot.timer != null) {
        globalThis.clearTimeout(slot.timer);
        slot.timer = null;
      }
    }
  }

  function release(): void {
    if (!held) return;
    held = false;
    for (const itemId of [...slots.keys()]) {
      const slot = slots.get(itemId);
      if (!slot) continue;
      if (slot.timer != null) {
        globalThis.clearTimeout(slot.timer);
        slot.timer = null;
      }
      if (inflight.has(itemId)) void pump(itemId, slot.gen);
      else startSend(itemId, false);
    }
  }

  function cancel(itemId: string): void {
    const slot = slots.get(itemId);
    if (!slot) return;
    if (slot.timer != null) globalThis.clearTimeout(slot.timer);
    slots.delete(itemId);
  }

  function hasPending(): boolean {
    return slots.size > 0;
  }

  function busy(): boolean {
    return slots.size > 0 || inflight.size > 0;
  }

  function cancelAll(): void {
    for (const itemId of [...slots.keys()]) cancel(itemId);
  }

  function pendingFields(itemId: string): Record<string, unknown> | undefined {
    const slot = slots.get(itemId);
    if (!slot) return undefined;
    return { ...slot.fields };
  }

  return {
    schedule,
    flush,
    flushKeepalive,
    hold,
    release,
    cancel,
    hasPending,
    busy,
    cancelAll,
    pendingFields,
  };
}

/** pagehide, beforeunload, and hidden visibilitychange start a keepalive flush. */
export function installUnloadFlush(
  queue: { flushKeepalive(): void },
  win: EventTarget,
  doc: { visibilityState: string } & EventTarget
): () => void {
  const onPageHide = () => {
    queue.flushKeepalive();
  };
  const onBeforeUnload = () => {
    queue.flushKeepalive();
  };
  const onVisibility = () => {
    if (doc.visibilityState === 'hidden') queue.flushKeepalive();
  };
  win.addEventListener('pagehide', onPageHide);
  win.addEventListener('beforeunload', onBeforeUnload);
  doc.addEventListener('visibilitychange', onVisibility);
  return () => {
    win.removeEventListener('pagehide', onPageHide);
    win.removeEventListener('beforeunload', onBeforeUnload);
    doc.removeEventListener('visibilitychange', onVisibility);
  };
}

/**
 * Await a full flush, log failures, then run `action` either way.
 * The wait is capped at `timeoutMs` so a hung server can't block close or reload forever.
 */
export async function flushThen(
  queue: { flush(): Promise<void> },
  action: () => unknown,
  timeoutMs = 3000
): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timedOut = new Promise<void>((resolve) => {
    timer = globalThis.setTimeout(() => {
      console.warn(`Pending saves did not finish within ${timeoutMs}ms; continuing`);
      resolve();
    }, timeoutMs);
  });
  try {
    await Promise.race([queue.flush(), timedOut]);
  } catch (err) {
    console.error(err);
  } finally {
    if (timer !== undefined) globalThis.clearTimeout(timer);
  }
  await action();
}
