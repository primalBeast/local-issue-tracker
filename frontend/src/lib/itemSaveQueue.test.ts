import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Item } from './api';
import {
  createItemSaveQueue,
  flushThen,
  installUnloadFlush,
  type ItemSaveRequest,
} from './itemSaveQueue';

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
});
