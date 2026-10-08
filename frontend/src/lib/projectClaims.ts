/** Tooltip and toast copy when another window holds the project. */
export const TAKEN_TITLE = 'Already open in another window';

export type ClaimsMap = Record<string, string>;

export type ClaimOutcome = { ok: true } | { ok: false; heldByOther: true };

export type PickerItemState = {
  disabled: boolean;
  title: string | undefined;
};

/** Minimal stream so tests can fake EventSource without a DOM. */
export type ClaimsStream = {
  addEventListener(type: string, listener: (ev: { data?: string }) => void): void;
  close(): void;
};

export type ProjectClaimsController = {
  connect(clientId: string): void;
  disconnect(): void;
  subscribe(listener: (claims: ClaimsMap) => void): () => void;
  claims(): ClaimsMap;
  takenByOther(slug: string): boolean;
  pickerItemState(slug: string, currentSlug?: string | null): PickerItemState;
  setCurrentProject(slug: string | null): void;
};

/**
 * True when `slug` is claimed by a client other than `clientId`.
 * Missing claims are free (header-less writes still work until someone claims).
 */
export function takenByOther(claims: ClaimsMap, clientId: string, slug: string): boolean {
  const holder = claims[slug];
  return Boolean(holder) && holder !== clientId;
}

/**
 * Picker row for `slug`. `currentSlug` is the project this window has open;
 * a project this client holds stays enabled. Another holder's project is
 * disabled with the exact tooltip.
 */
export function pickerItemState(
  claims: ClaimsMap,
  clientId: string,
  slug: string,
  currentSlug?: string | null
): PickerItemState {
  if (takenByOther(claims, clientId, slug)) {
    return { disabled: true, title: TAKEN_TITLE };
  }
  if (currentSlug && slug === currentSlug) {
    return { disabled: false, title: undefined };
  }
  return { disabled: false, title: undefined };
}

function parseClaims(data: string | undefined): ClaimsMap | null {
  if (!data) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object' || !('claims' in parsed)) return null;
  const raw = (parsed as { claims: unknown }).claims;
  if (!raw || typeof raw !== 'object') return null;
  const next: ClaimsMap = {};
  for (const [slug, holder] of Object.entries(raw)) {
    if (typeof holder === 'string') next[slug] = holder;
  }
  return next;
}

/**
 * Live project claims from the session event stream.
 * No polling. Reconnect after an error re-claims the project this window had
 * open; the browser EventSource reconnects on its own.
 */
export function createProjectClaims(deps: {
  openEventSource: (url: string) => ClaimsStream;
  claimProject: (slug: string) => Promise<ClaimOutcome>;
  onLost?: (slug: string) => void;
}): ProjectClaimsController {
  let clientId = '';
  let claims: ClaimsMap = {};
  let currentSlug: string | null = null;
  let source: ClaimsStream | null = null;
  let sawError = false;
  let reassertGen = 0;
  const subs = new Set<(claims: ClaimsMap) => void>();

  function notify(): void {
    const snapshot = claims;
    for (const fn of subs) fn(snapshot);
  }

  async function reassert(slug: string): Promise<void> {
    const gen = ++reassertGen;
    let result: ClaimOutcome;
    try {
      result = await deps.claimProject(slug);
    } catch (err) {
      console.error(err);
      return;
    }
    if (gen !== reassertGen || currentSlug !== slug) return;
    if (!result.ok && result.heldByOther) deps.onLost?.(slug);
  }

  function connect(id: string): void {
    disconnect();
    clientId = id;
    sawError = false;
    const stream = deps.openEventSource(
      `/api/session/events?client=${encodeURIComponent(id)}`
    );
    source = stream;
    stream.addEventListener('claims', (ev) => {
      if (source !== stream) return;
      const next = parseClaims(ev.data);
      if (!next) return;
      claims = next;
      notify();
    });
    stream.addEventListener('open', () => {
      if (source !== stream) return;
      const reconnect = sawError;
      sawError = false;
      if (reconnect && currentSlug) void reassert(currentSlug);
    });
    stream.addEventListener('error', () => {
      if (source !== stream) return;
      sawError = true;
    });
  }

  function disconnect(): void {
    const stream = source;
    source = null;
    sawError = false;
    stream?.close();
  }

  function subscribe(listener: (next: ClaimsMap) => void): () => void {
    subs.add(listener);
    listener(claims);
    return () => {
      subs.delete(listener);
    };
  }

  return {
    connect,
    disconnect,
    subscribe,
    claims: () => claims,
    takenByOther: (slug) => takenByOther(claims, clientId, slug),
    pickerItemState: (slug, current) => pickerItemState(claims, clientId, slug, current),
    setCurrentProject: (slug) => {
      currentSlug = slug;
    },
  };
}

/** Adapt the browser EventSource to the tiny stream the controller needs. */
export function browserClaimsStream(url: string): ClaimsStream {
  const source = new EventSource(url);
  return {
    addEventListener(type, listener) {
      source.addEventListener(type, (ev: Event) => {
        let data: string | undefined;
        if ('data' in ev && typeof (ev as MessageEvent).data === 'string') {
          data = (ev as MessageEvent).data;
        }
        listener({ data });
      });
    },
    close() {
      source.close();
    },
  };
}
