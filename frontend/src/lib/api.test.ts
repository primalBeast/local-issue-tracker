import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, getClientId, setClientId } from './api';

afterEach(() => {
  setClientId(null);
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
