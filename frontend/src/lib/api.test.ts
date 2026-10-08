import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
});

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
