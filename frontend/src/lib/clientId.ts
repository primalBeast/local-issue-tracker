/** sessionStorage key. Survives F5 in this window; a new window gets its own id. */
export const CLIENT_ID_STORAGE_KEY = 'lit.clientId';

const CLIENT_ID_RE = /^[A-Za-z0-9_-]{8,64}$/;

export type ClientIdStorage = Pick<Storage, 'getItem' | 'setItem'>;

/**
 * Client id for this window. Stable across reload (same sessionStorage),
 * new when storage is empty (another window or tab).
 */
export function getClientId(storage: ClientIdStorage = sessionStorage): string {
  try {
    const existing = storage.getItem(CLIENT_ID_STORAGE_KEY);
    if (existing && CLIENT_ID_RE.test(existing)) return existing;
  } catch {
    /* private mode or a locked storage */
  }
  const id = mintClientId();
  try {
    storage.setItem(CLIENT_ID_STORAGE_KEY, id);
  } catch {
    /* ignore quota / private mode */
  }
  return id;
}

function mintClientId(): string {
  const cryptoObj = globalThis.crypto;
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    try {
      const id = cryptoObj.randomUUID();
      if (CLIENT_ID_RE.test(id)) return id;
    } catch {
      /* fall through to getRandomValues / Math.random */
    }
  }
  const bytes = new Uint8Array(16);
  if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  let hex = '';
  for (const byte of bytes) hex += byte.toString(16).padStart(2, '0');
  return hex;
}
