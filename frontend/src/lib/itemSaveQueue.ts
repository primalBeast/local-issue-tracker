import { itemPatchBody, type Item } from './api';
import { bodyByteLength, KEEPALIVE_BUDGET_BYTES } from './keepaliveBudget';

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
  /** True while a save is queued, a PATCH is in flight, or a 409 retry is running. */
  busy(): boolean;
  /** Drop every queued edit without sending. In-flight PATCHes are left alone. */
  cancelAll(): void;
  /** Fields queued for `itemId` that have not been sent yet. */
  pendingFields(itemId: string): Record<string, unknown> | undefined;
  /** True when a queued or in-flight save is over the keepalive body budget. */
  hasLargeSave(): boolean;
};

type Slot = {
  slug: string;
  fields: Record<string, unknown>;
  timer: ReturnType<typeof setTimeout> | null;
  /** Bumped on every schedule so a waiter can see that the batch changed. */
  gen: number;
  /**
   * `flush()` epoch that parked this slot after a failed 409 retry.
   * The flush that just failed must not immediately send it again.
   */
  skipFlushEpoch?: number;
};

type QueueOptions = {
  delayMs?: number;
  send(req: ItemSaveRequest): Promise<Item>;
  getVersion(itemId: string): number | undefined;
  onSaved(itemId: string, item: Item, slug: string): void;
  onError(itemId: string, slug: string, err: unknown): void | Promise<void>;
  /** Load the server copy after a 409 so the edit can be retried once. */
  fetchLatest?(slug: string, itemId: string): Promise<Item>;
  /** 409 retry failed. The edit stays queued; show a toast rather than reloading. */
  onConflictKept?(itemId: string, slug: string): void;
  /** Defaults to `status === 409`. */
  isConflict?(err: unknown): boolean;
  /** Defaults to `status === 423`. Lock errors keep today's drop path. */
  isLocked?(err: unknown): boolean;
};

function statusOf(err: unknown): number | undefined {
  if (!err || typeof err !== 'object' || !('status' in err)) return undefined;
  const status = (err as { status: unknown }).status;
  return typeof status === 'number' ? status : undefined;
}

export function createItemSaveQueue(opts: QueueOptions): ItemSaveQueue {
  const delayMs = opts.delayMs ?? 350;
  const slots = new Map<string, Slot>();
  /** Per item, resolves after that item's sends (and their onSaved/onError) settle. */
  const inflight = new Map<string, Promise<void>>();
  let held = false;
  let largeInflight = 0;
  let flushEpoch = 0;

  function isConflict(err: unknown): boolean {
    if (opts.isConflict) return opts.isConflict(err);
    return statusOf(err) === 409;
  }

  function isLocked(err: unknown): boolean {
    if (opts.isLocked) return opts.isLocked(err);
    return statusOf(err) === 423;
  }

  function oversized(fields: Record<string, unknown>, version: number | undefined): boolean {
    return bodyByteLength(itemPatchBody(fields, version)) > KEEPALIVE_BUDGET_BYTES;
  }

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

  function consumeSlot(itemId: string): Record<string, unknown> {
    const slot = slots.get(itemId);
    if (!slot) return {};
    const fields = { ...slot.fields };
    if (slot.timer != null) globalThis.clearTimeout(slot.timer);
    slots.delete(itemId);
    return fields;
  }

  /**
   * Put a failed edit back. Newer keys already queued win.
   * A flush that is still looping will not send this slot again; a later
   * schedule or flush will.
   */
  function parkFailedEdit(slug: string, itemId: string, fields: Record<string, unknown>): void {
    const existed = slots.has(itemId);
    let slot = slots.get(itemId);
    if (!slot) {
      slot = { slug, fields: {}, timer: null, gen: 0 };
      slots.set(itemId, slot);
    }
    slot.slug = slug;
    slot.fields = { ...fields, ...slot.fields };
    slot.gen += 1;
    slot.skipFlushEpoch = flushEpoch;
    if (slot.timer != null) {
      globalThis.clearTimeout(slot.timer);
      slot.timer = null;
    }
    if (existed && !held) arm(itemId);
  }

  async function reportError(itemId: string, slug: string, err: unknown): Promise<void> {
    try {
      await opts.onError(itemId, slug, err);
    } catch (handlerErr) {
      console.error(handlerErr);
    }
  }

  /**
   * One retry: read the latest item, overlay only our pending keys, send with
   * that version. A second failure stays queued and does not reload the item.
   */
  async function recoverConflict(
    slug: string,
    itemId: string,
    failedFields: Record<string, unknown>
  ): Promise<void> {
    if (!opts.fetchLatest) {
      await reportError(itemId, slug, new Error('version conflict'));
      return;
    }
    let latest: Item;
    try {
      latest = await opts.fetchLatest(slug, itemId);
    } catch (err) {
      if (isLocked(err)) {
        await reportError(itemId, slug, err);
        return;
      }
      parkFailedEdit(slug, itemId, failedFields);
      opts.onConflictKept?.(itemId, slug);
      return;
    }

    const newer = consumeSlot(itemId);
    const retryFields = { ...failedFields, ...newer };
    try {
      const saved = await opts.send({
        slug,
        itemId,
        fields: retryFields,
        version: latest.version,
        keepalive: false,
      });
      try {
        opts.onSaved(itemId, saved, slug);
      } catch (err) {
        console.error(err);
      }
    } catch (err) {
      if (isLocked(err)) {
        await reportError(itemId, slug, err);
        return;
      }
      parkFailedEdit(slug, itemId, retryFields);
      opts.onConflictKept?.(itemId, slug);
    }
  }

  async function handleFailure(
    slug: string,
    itemId: string,
    fields: Record<string, unknown>,
    err: unknown
  ): Promise<void> {
    if (isConflict(err) && opts.fetchLatest) {
      await recoverConflict(slug, itemId, fields);
      return;
    }
    await reportError(itemId, slug, err);
  }

  /**
   * Start the PATCH now. `send` is called synchronously so a keepalive flush
   * still reaches fetch while the page is unloading.
   * Version is omitted only for that close-time keepalive flush when this
   * item already has a save in flight: both edits are ours, and the server
   * skips the check so the last write wins. Every other send includes
   * `getVersion`. Non-keepalive callers do not overlap an in-flight save
   * for the same item: schedule arms the debounce, flush retries only after
   * the current PATCH settles, and release goes through pump, which sends
   * once that PATCH has settled. The 409 retry is not another startSend;
   * it carries the version just fetched and runs inside the failed attempt's
   * gate, after that attempt's request has settled.
   */
  function startSend(itemId: string, keepalive: boolean): Promise<void> {
    const slot = slots.get(itemId);
    if (!slot) return Promise.resolve();
    const ownSaveInFlight = inflight.has(itemId);
    slots.delete(itemId);
    if (slot.timer != null) {
      globalThis.clearTimeout(slot.timer);
      slot.timer = null;
    }
    const { slug, fields } = slot;
    const version = keepalive && ownSaveInFlight ? undefined : opts.getVersion(itemId);
    const large = oversized(fields, version);
    const useKeepalive = keepalive && !large;
    if (large) largeInflight += 1;

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
        () => {
          if (large) largeInflight -= 1;
          resolveGate();
        },
        (err) => {
          if (large) largeInflight -= 1;
          console.error(err);
          resolveGate();
        }
      );
    };

    try {
      const sent = opts.send({ slug, itemId, fields, version, keepalive: useKeepalive });
      finish(
        Promise.resolve(sent).then(
          (saved) => {
            try {
              opts.onSaved(itemId, saved, slug);
            } catch (err) {
              console.error(err);
            }
          },
          (err: unknown) => handleFailure(slug, itemId, fields, err)
        )
      );
    } catch (err) {
      finish(handleFailure(slug, itemId, fields, err));
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
    slot.skipFlushEpoch = undefined;
    if (slot.timer != null) {
      globalThis.clearTimeout(slot.timer);
      slot.timer = null;
    }
    if (held) return;
    // Skip the debounce only when the body cannot use keepalive and this
    // item has no save in flight. An in-flight PATCH must finish first so
    // the merged batch is sent with the version that save just stored.
    const version = opts.getVersion(itemId);
    if (oversized(slot.fields, version) && !inflight.has(itemId)) {
      startSend(itemId, false);
      return;
    }
    arm(itemId);
  }

  async function flush(): Promise<void> {
    const epoch = ++flushEpoch;
    for (let guard = 0; guard < 100; guard += 1) {
      for (const itemId of [...slots.keys()]) {
        const slot = slots.get(itemId);
        if (!slot || slot.skipFlushEpoch === epoch) continue;
        if (slot.timer != null) {
          globalThis.clearTimeout(slot.timer);
          slot.timer = null;
        }
        if (!inflight.has(itemId)) startSend(itemId, false);
      }
      if (inflight.size === 0) return;
      await Promise.all([...inflight.values()]);
      const more = [...slots.values()].some((slot) => slot.skipFlushEpoch !== epoch);
      if (!more && inflight.size === 0) return;
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

  function hasLargeSave(): boolean {
    if (largeInflight > 0) return true;
    for (const [itemId, slot] of slots) {
      // Same version a keepalive flush would send right now. A normal send
      // waits until this item is idle, then includes getVersion.
      const version = inflight.has(itemId) ? undefined : opts.getVersion(itemId);
      if (oversized(slot.fields, version)) return true;
    }
    return false;
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
    hasLargeSave,
  };
}

export type UnloadFlushOptions = {
  /** Extra work after the item keepalive flush (board layout). */
  onUnload?: () => void;
  /**
   * Return true to show the browser leave-page prompt.
   * Called after the flush has started. Callers must return false inside
   * pywebview: beforeunload can fire on destroy and a prompt would block
   * the X / Alt+F4 close, which uses the bounded flush instead.
   */
  shouldPrompt?: () => boolean;
};

/** pagehide, beforeunload, and hidden visibilitychange start a keepalive flush. */
export function installUnloadFlush(
  queue: { flushKeepalive(): void },
  win: EventTarget,
  doc: { visibilityState: string } & EventTarget,
  options?: UnloadFlushOptions
): () => void {
  const flush = () => {
    queue.flushKeepalive();
    options?.onUnload?.();
  };
  const onPageHide = () => {
    flush();
  };
  const onBeforeUnload = (event: Event) => {
    flush();
    if (!options?.shouldPrompt?.()) return;
    event.preventDefault();
    // BeforeUnloadEvent.returnValue is what shows the browser prompt. Node's
    // Event type has no setter, so the cast goes through unknown.
    (event as unknown as { returnValue: string }).returnValue = '';
  };
  const onVisibility = () => {
    if (doc.visibilityState === 'hidden') flush();
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
