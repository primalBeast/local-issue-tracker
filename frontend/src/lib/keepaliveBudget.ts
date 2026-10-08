/** Headroom under the browser's 64 KiB cap on in-flight `keepalive` bodies. */
export const KEEPALIVE_BUDGET_BYTES = 60_000;

const encoder = new TextEncoder();

/** UTF-8 size of a request body. Multibyte characters count as more than one. */
export function bodyByteLength(body: string): number {
  return encoder.encode(body).length;
}

export type KeepaliveBudget = {
  /** Bytes currently reserved by in-flight keepalive requests. */
  used(): number;
  /**
   * Reserve `bytes` against the shared cap.
   * Returns a release function, or null when the body does not fit.
   * The release function is safe to call more than once.
   */
  tryReserve(bytes: number): (() => void) | null;
};

export function createKeepaliveBudget(limit = KEEPALIVE_BUDGET_BYTES): KeepaliveBudget {
  let usedBytes = 0;
  return {
    used: () => usedBytes,
    tryReserve(bytes: number) {
      if (!Number.isFinite(bytes) || bytes < 0) return null;
      if (usedBytes + bytes > limit) return null;
      usedBytes += bytes;
      let open = true;
      return () => {
        if (!open) return;
        open = false;
        usedBytes -= bytes;
      };
    },
  };
}

let sharedBudget = createKeepaliveBudget();

/** Reserve against the process-wide keepalive cap shared by every API call. */
export function reserveSharedKeepalive(bytes: number): (() => void) | null {
  return sharedBudget.tryReserve(bytes);
}

/** Drop reservations. Tests use this so one case cannot starve the next. */
export function resetSharedKeepaliveBudget(): void {
  sharedBudget = createKeepaliveBudget();
}
