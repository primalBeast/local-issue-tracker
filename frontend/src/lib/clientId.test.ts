import { afterEach, describe, expect, it, vi } from 'vitest';
import { CLIENT_ID_STORAGE_KEY, getClientId, type ClientIdStorage } from './clientId';

function memoryStorage(): ClientIdStorage {
  const data = new Map<string, string>();
  return {
    getItem: (key) => (data.has(key) ? (data.get(key) ?? null) : null),
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getClientId', () => {
  it('is stable across reads of the same storage and new for a fresh storage', () => {
    const windowA = memoryStorage();
    const windowB = memoryStorage();
    const first = getClientId(windowA);
    const reloaded = getClientId(windowA);
    expect(reloaded).toBe(first);
    expect(first).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(windowA.getItem(CLIENT_ID_STORAGE_KEY)).toBe(first);

    const other = getClientId(windowB);
    expect(other).not.toBe(first);
    expect(other).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it('keeps a valid stored id and replaces an invalid one', () => {
    const storage = memoryStorage();
    storage.setItem(CLIENT_ID_STORAGE_KEY, 'window_A-1');
    expect(getClientId(storage)).toBe('window_A-1');

    storage.setItem(CLIENT_ID_STORAGE_KEY, 'nope');
    const minted = getClientId(storage);
    expect(minted).not.toBe('nope');
    expect(minted).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(storage.getItem(CLIENT_ID_STORAGE_KEY)).toBe(minted);
  });

  it('mints a valid id when crypto.randomUUID is missing', () => {
    const real = globalThis.crypto;
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => real.getRandomValues(bytes),
    });
    const storage = memoryStorage();
    const id = getClientId(storage);
    expect(id).toMatch(/^[a-f0-9]{32}$/);
    expect(getClientId(storage)).toBe(id);
  });
});
