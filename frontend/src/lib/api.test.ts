import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, getClientId, itemPatchBody, setClientId, type Workspace } from './api';
import { bodyByteLength, resetSharedKeepaliveBudget } from './keepaliveBudget';

afterEach(() => {
  setClientId(null);
  resetSharedKeepaliveBudget();
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown, statusText = 'OK') {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: async () => body,
  };
}

describe('patchItem', () => {
  it('passes keepalive: true to fetch when asked and omits it otherwise', async () => {
    const fetchMock = vi.fn(async (_input: string, _init: RequestInit) => ({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({ id: 'item-1', version: 5 }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    await api.patchItem('demo', 'item-1', { title: 'a', urgency: 2 }, 4, { keepalive: true });
    await api.patchItem('demo', 'item-1', { title: 'b' }, 5);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const firstInit = fetchMock.mock.calls[0][1];
    const secondInit = fetchMock.mock.calls[1][1];
    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/demo/items/item-1');
    expect(firstInit.method).toBe('PATCH');
    expect(firstInit.keepalive).toBe(true);
    expect(JSON.parse(String(firstInit.body))).toEqual({
      fields: { title: 'a', urgency: 2 },
      version: 4,
    });
    expect(secondInit.method).toBe('PATCH');
    expect(secondInit).not.toHaveProperty('keepalive');
    expect(JSON.parse(String(secondInit.body))).toEqual({
      fields: { title: 'b' },
      version: 5,
    });
  });

  it('omits version when it is null or undefined so the server skips the check', async () => {
    const fetchMock = vi.fn(async (_input: string, _init: RequestInit) =>
      jsonResponse(200, { id: 'item-1', version: 2 })
    );
    vi.stubGlobal('fetch', fetchMock);

    expect(itemPatchBody({ title: 'a' }, undefined)).toBe(JSON.stringify({ fields: { title: 'a' } }));
    expect(itemPatchBody({ title: 'b' }, null)).toBe(JSON.stringify({ fields: { title: 'b' } }));

    await api.patchItem('demo', 'item-1', { title: 'a' });
    await api.patchItem('demo', 'item-1', { title: 'b' }, null);

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ fields: { title: 'a' } });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ fields: { title: 'b' } });
    expect(String(fetchMock.mock.calls[0][1]?.body)).not.toContain('version');
    expect(String(fetchMock.mock.calls[1][1]?.body)).not.toContain('version');
  });

  it('sends an over-budget keepalive body as a normal fetch', async () => {
    const fetchMock = vi.fn(async (_input: string, _init: RequestInit) =>
      jsonResponse(200, { id: 'item-1', version: 2 })
    );
    vi.stubGlobal('fetch', fetchMock);
    const notes = 'x'.repeat(70_000);

    await api.patchItem('demo', 'item-1', { notes }, 1, { keepalive: true });
    await api.putWorkspace(
      'demo',
      'ws-1',
      { id: 'ws-1', name: notes } as unknown as Workspace,
      { keepalive: true }
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]?.keepalive).not.toBe(true);
    expect(fetchMock.mock.calls[1][1]?.keepalive).not.toBe(true);
    expect(bodyByteLength(String(fetchMock.mock.calls[0][1]?.body))).toBeGreaterThan(60_000);
    expect(bodyByteLength(String(fetchMock.mock.calls[1][1]?.body))).toBeGreaterThan(60_000);
  });

  it('keeps the first of two 40 KB keepalive bodies and sends the second as a normal fetch', async () => {
    const notes = 'x'.repeat(40_000);
    let releaseFetch: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      releaseFetch = resolve;
    });
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      gate.then(() => jsonResponse(200, { id: 'item-1', version: 2, fields: {} }))
    );
    vi.stubGlobal('fetch', fetchMock);

    const first = api.patchItem('demo', 'a', { notes }, 1, { keepalive: true });
    const second = api.patchItem('demo', 'b', { notes }, 1, { keepalive: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]?.keepalive).toBe(true);
    expect(fetchMock.mock.calls[1][1]?.keepalive).not.toBe(true);

    releaseFetch();
    await Promise.all([first, second]);

    await api.patchItem('demo', 'c', { notes }, 1, { keepalive: true });
    expect(fetchMock.mock.calls[2][1]?.keepalive).toBe(true);
  });

  it('retries a keepalive TypeError once as a normal fetch', async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.keepalive) return Promise.reject(new TypeError('Failed to fetch'));
      return Promise.resolve(jsonResponse(200, { id: 'item-1', version: 2 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.patchItem('demo', 'item-1', { title: 'a' }, 1, { keepalive: true });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]?.keepalive).toBe(true);
    expect(fetchMock.mock.calls[1][1]?.keepalive).not.toBe(true);
  });

  it('retries when keepalive fetch throws synchronously and releases the budget', async () => {
    const notes = 'x'.repeat(40_000);
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.keepalive && String(init.body).includes('first')) {
        throw new Error('keepalive rejected by browser');
      }
      return Promise.resolve(jsonResponse(200, { id: 'item-1', version: 2 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.patchItem('demo', 'item-1', { notes: `first-${notes}` }, 1, { keepalive: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]?.keepalive).toBe(true);
    expect(fetchMock.mock.calls[1][1]?.keepalive).not.toBe(true);

    await api.patchItem('demo', 'item-2', { notes }, 1, { keepalive: true });
    expect(fetchMock.mock.calls[2][1]?.keepalive).toBe(true);
  });

  it('does not retry a keepalive rejection that is not a TypeError, and releases the budget', async () => {
    const notes = 'x'.repeat(40_000);
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.keepalive && String(init.body).includes('offline')) {
        return Promise.reject(new Error('offline'));
      }
      return Promise.resolve(jsonResponse(200, { id: 'item-1', version: 2 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      api.patchItem('demo', 'item-1', { notes: `offline-${notes}` }, 1, { keepalive: true })
    ).rejects.toThrow('offline');
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await api.patchItem('demo', 'item-2', { notes }, 1, { keepalive: true });
    expect(fetchMock.mock.calls[1][1]?.keepalive).toBe(true);
  });
});

describe('client header and project claims', () => {
  it('sends X-Lit-Client on ordinary requests and on keepalive patchItem', async () => {
    setClientId('client-123');
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, []));
    vi.stubGlobal('fetch', fetchMock);

    await api.projects();
    await api.patchItem('demo', 'item-1', { title: 'a' }, 4, { keepalive: true });

    expect(getClientId()).toBe('client-123');
    const listInit = fetchMock.mock.calls[0][1];
    const patchInit = fetchMock.mock.calls[1][1];
    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects');
    expect(new Headers(listInit?.headers).get('X-Lit-Client')).toBe('client-123');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/projects/demo/items/item-1');
    expect(new Headers(patchInit?.headers).get('X-Lit-Client')).toBe('client-123');
    expect(patchInit?.keepalive).toBe(true);
    expect(patchInit?.method).toBe('PATCH');
  });

  it('omits X-Lit-Client until a client id is set', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, []));
    vi.stubGlobal('fetch', fetchMock);
    await api.projects();
    const init = fetchMock.mock.calls[0][1];
    expect(new Headers(init?.headers).get('X-Lit-Client')).toBeNull();
  });

  it('claimProject maps HTTP 409 to heldByOther and returns ok otherwise', async () => {
    setClientId('client-123');
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
      if (url.includes('/claim-taken/')) {
        return jsonResponse(409, { held_by_other: true, detail: 'Already open in another window' }, 'Conflict');
      }
      return jsonResponse(200, { slug: 'demo', holder: 'client-123', claims: {} });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.claimProject('claim-taken')).resolves.toEqual({ ok: false, heldByOther: true });
    await expect(api.claimProject('demo')).resolves.toEqual({ ok: true });
    const takenInit = fetchMock.mock.calls[0][1];
    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/claim-taken/claim');
    expect(takenInit?.method).toBe('POST');
    expect(new Headers(takenInit?.headers).get('X-Lit-Client')).toBe('client-123');
  });

  it('releaseAll posts /api/session/release-all for this client', async () => {
    setClientId('client-123');
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      jsonResponse(200, { released: ['demo'] })
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.releaseAll({ keepalive: true })).resolves.toEqual({ released: ['demo'] });
    const init = fetchMock.mock.calls[0][1];
    expect(fetchMock.mock.calls[0][0]).toBe('/api/session/release-all?client=client-123');
    expect(init?.method).toBe('POST');
    expect(init?.keepalive).toBe(true);
    expect(new Headers(init?.headers).get('X-Lit-Client')).toBe('client-123');
  });

  it('GET /api/session/claims returns the snapshot', async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
      jsonResponse(200, { claims: { demo: 'client-123' } })
    );
    vi.stubGlobal('fetch', fetchMock);
    await expect(api.claims()).resolves.toEqual({ claims: { demo: 'client-123' } });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/session/claims');
  });

  it('throws ApiError 423 whose message says the project is open in another window', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(423, { detail: 'Project is open in another window' }, 'Locked')
    );
    vi.stubGlobal('fetch', fetchMock);
    const err = await api.patchItem('demo', 'item-1', { title: 'a' }, 1).then(
      () => null,
      (caught: unknown) => caught
    );
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 423 });
    expect((err as Error).message).toMatch(/open in another window/);
  });
});
