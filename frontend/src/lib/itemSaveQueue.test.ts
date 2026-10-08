import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Item } from './api';
import {
  createItemSaveQueue,
  flushThen,
  installUnloadFlush,
  type ItemSaveRequest,
} from './itemSaveQueue';

/** Node's Event.returnValue is a read-only getter. BeforeUnloadEvent's is writable. */
function beforeUnloadEvent(): Event & { returnValue: string | boolean } {
  const event = new Event('beforeunload', { cancelable: true });
  let returnValue: string | boolean = true;
  Object.defineProperty(event, 'returnValue', {
    configurable: true,
    enumerable: true,
    get: () => returnValue,
    set: (value: string | boolean) => {
      returnValue = value;
    },
  });
  return event as Event & { returnValue: string | boolean };
}

function saved(partial: Partial<Item> & { version: number }): Item {
  return {
    id: partial.id ?? 'id',
    sort_key: 0,
    fields: partial.fields ?? {},
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: '2026-01-01T00:00:00.000Z',
    version: partial.version,
    waiting: partial.waiting ?? {
      is_waiting: false,
      current_started_at: null,
      current_seconds: null,
      total_seconds: 0,
    },
  };
}

describe('item save queue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('merges two field edits within 350ms into one PATCH with both keys', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 8, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 7,
      onSaved: () => {},
      onError: () => {},
    });

    queue.schedule('proj', 'item-1', { description: 'hello' });
    await vi.advanceTimersByTimeAsync(180);
    queue.schedule('proj', 'item-1', { urgency: 2 });
    await vi.advanceTimersByTimeAsync(180);
    expect(send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(170);

    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      fields: { description: 'hello', urgency: 2 },
      version: 7,
      keepalive: false,
    });
  });

  it('later key wins when the same field is edited twice; separate items get separate requests; slug captured at schedule time', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 3,
      onSaved: () => {},
      onError: () => {},
    });

    queue.schedule('alpha', 'i1', { title: 'old', notes: 'keep' });
    queue.schedule('alpha', 'i1', { title: 'new' });
    queue.schedule('beta', 'i2', { urgency: 9 });
    await vi.advanceTimersByTimeAsync(350);

    expect(send).toHaveBeenCalledTimes(2);
    const first = send.mock.calls.find((call) => call[0].itemId === 'i1')?.[0];
    const second = send.mock.calls.find((call) => call[0].itemId === 'i2')?.[0];
    expect(first).toMatchObject({
      slug: 'alpha',
      fields: { title: 'new', notes: 'keep' },
      version: 3,
    });
    expect(second).toMatchObject({
      slug: 'beta',
      itemId: 'i2',
      fields: { urgency: 9 },
      version: 3,
    });
  });

  it('version chaining: a second patch scheduled while the first is in flight waits and uses the version from the first response', async () => {
    let version = 1;
    let releaseFirst: ((item: Item) => void) | null = null;
    const order: string[] = [];
    let calls = 0;
    const send = vi.fn((req: ItemSaveRequest) => {
      calls += 1;
      order.push(`send:${req.version}`);
      if (calls === 1) {
        return new Promise<Item>((resolve) => {
          releaseFirst = resolve;
        });
      }
      return Promise.resolve(
        saved({ version: (req.version ?? 0) + 1, id: req.itemId, fields: req.fields })
      );
    });
    const queue = createItemSaveQueue({
      send,
      getVersion: () => version,
      onSaved: (_id, item) => {
        order.push(`saved:${item.version}`);
        version = item.version;
      },
      onError: () => {},
    });

    queue.schedule('proj', 'item-1', { description: 'first' });
    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      version: 1,
      fields: { description: 'first' },
    });

    queue.schedule('proj', 'item-1', { urgency: 4 });
    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(1);

    releaseFirst!(saved({ version: 8, id: 'item-1', fields: { description: 'first' } }));
    await vi.advanceTimersByTimeAsync(0);

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      version: 8,
      fields: { urgency: 4 },
    });
    expect(order.slice(0, 3)).toEqual(['send:1', 'saved:8', 'send:8']);
  });

  it('flushKeepalive sends pending patches immediately with keepalive: true', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 4,
      onSaved: () => {},
      onError: () => {},
    });

    queue.schedule('alpha', 'i1', { description: 'd' });
    queue.schedule('beta', 'i2', { urgency: 1 });
    expect(send).not.toHaveBeenCalled();
    queue.flushKeepalive();

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls.map((call) => call[0])).toEqual([
      expect.objectContaining({
        slug: 'alpha',
        itemId: 'i1',
        fields: { description: 'd' },
        version: 4,
        keepalive: true,
      }),
      expect.objectContaining({
        slug: 'beta',
        itemId: 'i2',
        fields: { urgency: 1 },
        version: 4,
        keepalive: true,
      }),
    ]);

    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('installUnloadFlush flushes keepalive on pagehide, beforeunload, and hidden visibilitychange', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });
    const win = new EventTarget();
    const doc = Object.assign(new EventTarget(), { visibilityState: 'visible' });
    const uninstall = installUnloadFlush(queue, win, doc);

    queue.schedule('s', 'a', { title: 'pagehide' });
    win.dispatchEvent(new Event('pagehide'));
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      keepalive: true,
      fields: { title: 'pagehide' },
    });

    queue.schedule('s', 'b', { title: 'beforeunload' });
    const before = new Event('beforeunload', { cancelable: true });
    win.dispatchEvent(before);
    expect(before.defaultPrevented).toBe(false);
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({
      keepalive: true,
      fields: { title: 'beforeunload' },
    });

    queue.schedule('s', 'c', { title: 'still-visible' });
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(send).toHaveBeenCalledTimes(2);

    doc.visibilityState = 'hidden';
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(send).toHaveBeenCalledTimes(3);
    expect(send.mock.calls[2][0]).toMatchObject({
      keepalive: true,
      fields: { title: 'still-visible' },
    });

    queue.schedule('s', 'd', { title: 'detached' });
    uninstall();
    win.dispatchEvent(new Event('pagehide'));
    win.dispatchEvent(new Event('beforeunload', { cancelable: true }));
    doc.visibilityState = 'hidden';
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(send).toHaveBeenCalledTimes(3);
  });

  it('flushThen awaits the pending save before closing', async () => {
    let resolveSend: ((item: Item) => void) | null = null;
    const send = vi.fn(
      (_req: ItemSaveRequest) =>
        new Promise<Item>((resolve) => {
          resolveSend = resolve;
        })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });
    queue.schedule('s', 'i1', { title: 'pending' });
    const action = vi.fn();
    const done = flushThen(queue, action);

    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      fields: { title: 'pending' },
      keepalive: false,
    });
    await Promise.resolve();
    expect(action).not.toHaveBeenCalled();

    resolveSend!(saved({ version: 2, id: 'i1', fields: { title: 'pending' } }));
    await done;
    expect(action).toHaveBeenCalledTimes(1);

    const failing = vi.fn(() => Promise.reject(new Error('nope')));
    const errorQueue = createItemSaveQueue({
      send: failing,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });
    errorQueue.schedule('s', 'i2', { title: 'bad' });
    const actionAfterError = vi.fn();
    await flushThen(errorQueue, actionAfterError);
    expect(failing).toHaveBeenCalledTimes(1);
    expect(actionAfterError).toHaveBeenCalledTimes(1);
  });

  it('flushThen still runs the action if a save hangs past the timeout', async () => {
    const send = vi.fn((_req: ItemSaveRequest) => new Promise<Item>(() => {}));
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });
    queue.schedule('s', 'i1', { title: 'stuck' });
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const action = vi.fn();
    const done = flushThen(queue, action, 3000);
    await vi.advanceTimersByTimeAsync(2999);
    expect(action).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await done;
    expect(send).toHaveBeenCalledTimes(1);
    expect(action).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it('drag: hold defers sends during the drag and release sends one PATCH per touched row', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 5,
      onSaved: () => {},
      onError: () => {},
    });

    queue.hold();
    queue.schedule('proj', 'a', { urgency: 2 });
    queue.schedule('proj', 'b', { urgency: 1 });
    queue.schedule('proj', 'a', { urgency: 3 });
    queue.schedule('proj', 'b', { urgency: 2 });
    queue.schedule('proj', 'c', { urgency: 4 });
    queue.schedule('proj', 'a', { urgency: 4 });
    queue.schedule('proj', 'c', { urgency: 3 });
    await vi.advanceTimersByTimeAsync(2000);
    expect(send).not.toHaveBeenCalled();

    queue.release();
    expect(send).toHaveBeenCalledTimes(3);
    const byId = Object.fromEntries(send.mock.calls.map((call) => [call[0].itemId, call[0]]));
    expect(byId.a).toMatchObject({ slug: 'proj', fields: { urgency: 4 }, version: 5, keepalive: false });
    expect(byId.b).toMatchObject({ slug: 'proj', fields: { urgency: 2 }, version: 5, keepalive: false });
    expect(byId.c).toMatchObject({ slug: 'proj', fields: { urgency: 3 }, version: 5, keepalive: false });
  });

  it('cancel drops a pending patch', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });

    queue.schedule('s', 'gone', { title: 'x' });
    queue.schedule('s', 'keep', { title: 'y' });
    expect(queue.hasPending()).toBe(true);
    queue.cancel('gone');
    expect(queue.hasPending()).toBe(true);
    await vi.advanceTimersByTimeAsync(350);

    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({ itemId: 'keep', fields: { title: 'y' } });
    queue.cancel('keep');
    expect(queue.hasPending()).toBe(false);
  });

  it('busy is true while a save is pending or in flight, and cancelAll drops queued edits', async () => {
    let resolveSend: (item: Item) => void = () => {};
    const send = vi.fn(
      () =>
        new Promise<Item>((resolve) => {
          resolveSend = resolve;
        })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
      delayMs: 10_000,
    });
    expect(queue.busy()).toBe(false);
    queue.schedule('s', 'i1', { title: 'a' });
    expect(queue.hasPending()).toBe(true);
    expect(queue.busy()).toBe(true);

    queue.cancelAll();
    expect(queue.busy()).toBe(false);
    expect(queue.hasPending()).toBe(false);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(send).not.toHaveBeenCalled();

    queue.schedule('s', 'i2', { title: 'b' });
    const flushing = queue.flush();
    expect(queue.hasPending()).toBe(false);
    expect(queue.busy()).toBe(true);
    expect(send).toHaveBeenCalledTimes(1);
    resolveSend(saved({ version: 2, id: 'i2', fields: { title: 'b' } }));
    await flushing;
    expect(queue.busy()).toBe(false);
  });

  it('flushKeepalive while a save is in flight sends the next save with no version', async () => {
    let releaseFirst: (item: Item) => void = () => {};
    const send = vi.fn((req: ItemSaveRequest) => {
      if (send.mock.calls.length === 1) {
        return new Promise<Item>((resolve) => {
          releaseFirst = resolve;
        });
      }
      return Promise.resolve(saved({ version: 5, id: req.itemId, fields: req.fields }));
    });
    const onSaved = vi.fn();
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 2,
      onSaved,
      onError: () => {},
    });

    queue.schedule('proj', 'item-1', { description: 'first' });
    await vi.advanceTimersByTimeAsync(350);
    expect(send.mock.calls[0][0].version).toBe(2);
    expect(onSaved).not.toHaveBeenCalled();

    queue.schedule('proj', 'item-1', { urgency: 4 });
    queue.flushKeepalive();
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0].version).toBeUndefined();
    expect(send.mock.calls[1][0].keepalive).toBe(true);
    expect(send.mock.calls[1][0].fields).toEqual({ urgency: 4 });
    expect(queue.busy()).toBe(true);

    releaseFirst(saved({ version: 3, id: 'item-1', fields: { description: 'first' } }));
    await vi.advanceTimersByTimeAsync(0);
    expect(onSaved).toHaveBeenCalledWith(
      'item-1',
      expect.objectContaining({ version: 3 }),
      'proj'
    );
    expect(onSaved).toHaveBeenCalledTimes(2);
    expect(queue.busy()).toBe(false);
  });

  it('retries a 409 once with the latest version and only the pending keys', async () => {
    const conflict = Object.assign(new Error('version conflict'), { status: 409 });
    let releaseLatest: (item: Item) => void = () => {};
    const fetchLatest = vi.fn(
      () =>
        new Promise<Item>((resolve) => {
          releaseLatest = resolve;
        })
    );
    const send = vi.fn((req: ItemSaveRequest) => {
      if (send.mock.calls.length === 1) return Promise.reject(conflict);
      return Promise.resolve(
        saved({ version: (req.version ?? 0) + 1, id: req.itemId, fields: req.fields })
      );
    });
    const onSaved = vi.fn();
    const onError = vi.fn();
    const onConflictKept = vi.fn();
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 4,
      onSaved,
      onError,
      fetchLatest: (slug, itemId) => {
        expect(slug).toBe('proj');
        expect(itemId).toBe('item-1');
        return fetchLatest();
      },
      onConflictKept,
    });

    queue.schedule('proj', 'item-1', { description: 'mine', urgency: 1 });
    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(1);
    expect(queue.busy()).toBe(true);
    expect(fetchLatest).toHaveBeenCalledTimes(1);

    queue.schedule('proj', 'item-1', { urgency: 5, title: 't' });
    releaseLatest(saved({ version: 9, id: 'item-1', fields: { description: 'server' } }));
    await vi.advanceTimersByTimeAsync(0);

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      version: 9,
      keepalive: false,
      fields: { description: 'mine', urgency: 5, title: 't' },
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(onConflictKept).not.toHaveBeenCalled();
    expect(queue.pendingFields('item-1')).toBeUndefined();
    expect(queue.busy()).toBe(false);
  });

  it('keeps the edit queued when a 409 retry also fails, and a later flush resends it', async () => {
    const conflict = Object.assign(new Error('version conflict'), { status: 409 });
    const send = vi.fn((_req: ItemSaveRequest): Promise<Item> => Promise.reject(conflict));
    const onError = vi.fn();
    const onConflictKept = vi.fn();
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 3,
      onSaved: () => {},
      onError,
      fetchLatest: async () => saved({ version: 9, id: 'item-1' }),
      onConflictKept,
    });

    queue.schedule('proj', 'item-1', { description: 'mine', notes: 'n' });
    await queue.flush();

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({
      version: 9,
      keepalive: false,
      fields: { description: 'mine', notes: 'n' },
    });
    expect(onConflictKept).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(queue.pendingFields('item-1')).toEqual({ description: 'mine', notes: 'n' });
    expect(queue.busy()).toBe(true);

    send.mockImplementation(async (req: ItemSaveRequest) =>
      saved({ version: 10, id: req.itemId, fields: req.fields })
    );
    await queue.flush();
    expect(send).toHaveBeenCalledTimes(3);
    expect(send.mock.calls[2][0]).toMatchObject({
      fields: { description: 'mine', notes: 'n' },
      version: 3,
    });
    expect(queue.pendingFields('item-1')).toBeUndefined();
    expect(queue.busy()).toBe(false);
  });

  it('leaves 423 and other failures on the existing error path', async () => {
    const errors = [
      Object.assign(new Error('Project is open in another window'), { status: 423 }),
      new Error('nope'),
    ];
    for (const err of errors) {
      const send = vi.fn(() => Promise.reject(err));
      const onError = vi.fn();
      const fetchLatest = vi.fn();
      const onConflictKept = vi.fn();
      const queue = createItemSaveQueue({
        send,
        getVersion: () => 1,
        onSaved: () => {},
        onError,
        fetchLatest,
        onConflictKept,
      });
      queue.schedule('s', 'i1', { title: 'x' });
      await vi.advanceTimersByTimeAsync(350);
      expect(fetchLatest).not.toHaveBeenCalled();
      expect(onConflictKept).not.toHaveBeenCalled();
      expect(onError).toHaveBeenCalledWith('i1', 's', err);
      expect(queue.pendingFields('i1')).toBeUndefined();
      expect(queue.busy()).toBe(false);
    }
  });

  it('sends an oversized save immediately as a normal fetch, including multibyte text', async () => {
    const send = vi.fn(async (req: ItemSaveRequest) =>
      saved({ version: 2, id: req.itemId, fields: req.fields })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });

    queue.schedule('s', 'ascii', { notes: 'x'.repeat(70_000) });
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0].keepalive).toBe(false);
    expect(send.mock.calls[0][0].version).toBe(1);
    expect(send.mock.calls[0][0].itemId).toBe('ascii');

    // 16k emoji is 32k UTF-16 code units but 64k UTF-8 bytes, over the 60 KB budget.
    queue.schedule('s', 'emoji', { notes: '😀'.repeat(16_000) });
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({ itemId: 'emoji', keepalive: false });

    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('oversized edits for one item wait for the in-flight save and keep its version', async () => {
    let version = 4;
    const notes = (mark: string) => `${mark}${'x'.repeat(70_000)}`;
    const active = new Map<string, number>();
    let maxConcurrency = 0;
    const pending: Array<(item: Item) => void> = [];
    const events: string[] = [];
    const send = vi.fn((req: ItemSaveRequest) => {
      const now = (active.get(req.itemId) ?? 0) + 1;
      active.set(req.itemId, now);
      maxConcurrency = Math.max(maxConcurrency, now);
      events.push(`start:${req.version ?? 'none'}:${String(req.fields.notes).slice(0, 1)}`);
      expect(req.version).toEqual(expect.any(Number));
      return new Promise<Item>((resolve) => {
        pending.push((item) => {
          active.set(req.itemId, (active.get(req.itemId) ?? 1) - 1);
          events.push(`end:${item.version}`);
          resolve(item);
        });
      });
    });
    const queue = createItemSaveQueue({
      send,
      getVersion: () => version,
      onSaved: (_id, item) => {
        version = item.version;
      },
      onError: () => {},
    });

    queue.schedule('proj', 'item-1', { notes: notes('a') });
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      version: 4,
      keepalive: false,
    });
    expect(String(send.mock.calls[0][0].fields.notes).startsWith('a')).toBe(true);

    queue.schedule('proj', 'item-1', { notes: notes('b') });
    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(1);
    expect(maxConcurrency).toBe(1);

    pending[0](saved({ version: 11, id: 'item-1', fields: {} }));
    await vi.advanceTimersByTimeAsync(0);

    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      version: 11,
      keepalive: false,
    });
    expect(String(send.mock.calls[1][0].fields.notes).startsWith('b')).toBe(true);
    expect(events).toEqual(['start:4:a', 'end:11', 'start:11:b']);

    queue.schedule('proj', 'item-1', { notes: notes('c') });
    queue.schedule('proj', 'item-1', { title: 'merged' });
    await vi.advanceTimersByTimeAsync(350);
    expect(send).toHaveBeenCalledTimes(2);
    expect(maxConcurrency).toBe(1);

    pending[1](saved({ version: 18, id: 'item-1', fields: {} }));
    await vi.advanceTimersByTimeAsync(0);

    expect(send).toHaveBeenCalledTimes(3);
    expect(send.mock.calls[2][0]).toMatchObject({
      slug: 'proj',
      itemId: 'item-1',
      version: 18,
      keepalive: false,
      fields: { title: 'merged' },
    });
    expect(String(send.mock.calls[2][0].fields.notes).startsWith('c')).toBe(true);
    expect(events).toEqual(['start:4:a', 'end:11', 'start:11:b', 'end:18', 'start:18:c']);
    expect(send.mock.calls.map((call) => call[0].version)).toEqual([4, 11, 18]);
    expect(maxConcurrency).toBe(1);

    pending[2](saved({ version: 19, id: 'item-1', fields: {} }));
    await vi.advanceTimersByTimeAsync(0);
    expect(queue.busy()).toBe(false);
  });

  it('flushKeepalive sends an oversized body without keepalive and keeps busy until it settles', async () => {
    let releaseSend: (item: Item) => void = () => {};
    const send = vi.fn(
      (_req: ItemSaveRequest) =>
        new Promise<Item>((resolve) => {
          releaseSend = resolve;
        })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });

    queue.hold();
    queue.schedule('s', 'big', { notes: 'x'.repeat(70_000) });
    expect(send).not.toHaveBeenCalled();
    expect(queue.hasLargeSave()).toBe(true);
    queue.flushKeepalive();
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0].keepalive).toBe(false);
    expect(queue.busy()).toBe(true);
    expect(queue.hasLargeSave()).toBe(true);

    releaseSend(saved({ version: 2, id: 'big', fields: {} }));
    await vi.advanceTimersByTimeAsync(0);
    expect(queue.busy()).toBe(false);
    expect(queue.hasLargeSave()).toBe(false);
  });

  it('beforeunload prompts only when a large save is outstanding and prompting is allowed', async () => {
    const resolvers: Array<(item: Item) => void> = [];
    const send = vi.fn(
      (req: ItemSaveRequest) =>
        new Promise<Item>((resolve) => {
          resolvers.push((item) => resolve({ ...item, id: req.itemId }));
        })
    );
    const queue = createItemSaveQueue({
      send,
      getVersion: () => 1,
      onSaved: () => {},
      onError: () => {},
    });
    const win = new EventTarget();
    const doc = Object.assign(new EventTarget(), { visibilityState: 'visible' });
    let allowPrompt = true;
    installUnloadFlush(queue, win, doc, {
      shouldPrompt: () => allowPrompt && queue.hasLargeSave(),
    });

    queue.schedule('s', 'small', { title: 'tiny' });
    const smallLeave = beforeUnloadEvent();
    win.dispatchEvent(smallLeave);
    expect(smallLeave.defaultPrevented).toBe(false);
    expect(smallLeave.returnValue).toBe(true);
    expect(send.mock.calls[0][0]).toMatchObject({ keepalive: true, fields: { title: 'tiny' } });

    queue.schedule('s', 'big', { notes: 'x'.repeat(70_000) });
    expect(queue.hasLargeSave()).toBe(true);
    const largeLeave = beforeUnloadEvent();
    win.dispatchEvent(largeLeave);
    expect(largeLeave.defaultPrevented).toBe(true);
    expect(largeLeave.returnValue).toBe('');

    const pageHide = new Event('pagehide', { cancelable: true });
    win.dispatchEvent(pageHide);
    expect(pageHide.defaultPrevented).toBe(false);

    allowPrompt = false;
    const webviewLeave = beforeUnloadEvent();
    win.dispatchEvent(webviewLeave);
    expect(webviewLeave.defaultPrevented).toBe(false);
    expect(webviewLeave.returnValue).toBe(true);

    for (const resolve of resolvers) resolve(saved({ version: 2, id: 'done' }));
    await vi.advanceTimersByTimeAsync(0);
    expect(queue.busy()).toBe(false);
  });
});
