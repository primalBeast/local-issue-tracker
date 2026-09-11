/** Build a launchable ticket URL from a project prefix + ticket key, or null. */
export function ticketHref(
  prefix: string | null | undefined,
  ticketKey: string | null | undefined
): string | null {
  const p = String(prefix ?? '').trim();
  const k = String(ticketKey ?? '').trim();
  if (!p || !k) return null;
  try {
    const base = new URL(p);
    if (base.protocol !== 'http:' && base.protocol !== 'https:') return null;
    if (!base.hostname) return null;
    const url = new URL(p + k);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!url.hostname) return null;
    return url.href;
  } catch {
    return null;
  }
}

/** Validate a complete URL for launching (http/https only). */
export function launchableHref(raw: string | null | undefined): string | null {
  const s = String(raw ?? '').trim();
  if (!s) return null;
  try {
    const url = new URL(s);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!url.hostname) return null;
    return url.href;
  } catch {
    return null;
  }
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function splitPane(href: string | null, title: string): string {
  const heading = escapeHtml(title);
  if (!href) {
    return `<section class="pane"><header>${heading}</header><p class="empty">No URL for this side. Set a project URL prefix for the master ticket.</p></section>`;
  }
  const src = escapeHtml(href);
  return `<section class="pane"><header><span>${heading}</span><a href="${src}" target="_blank" rel="noopener noreferrer">Open</a></header><iframe src="${src}" title="${heading}"></iframe></section>`;
}

/** HTML for a two-pane window: master ticket left, external ticket right. */
export function splitTicketViewHtml(
  masterHref: string | null | undefined,
  externalHref: string | null | undefined
): string | null {
  const right = launchableHref(externalHref);
  if (!right) return null;
  const left = launchableHref(masterHref);
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Split tickets</title>
  <style>
    html, body { margin: 0; height: 100%; background: #0b0d12; color: #e8eaed; font: 13px/1.4 system-ui, sans-serif; }
    .split { display: flex; height: 100%; }
    .pane { flex: 1 1 50%; min-width: 0; display: flex; flex-direction: column; }
    .pane + .pane { border-left: 3px solid #3a4458; }
    header { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; background: #12151c; border-bottom: 1px solid #2a3140; }
    header a { color: #6ea8fe; text-decoration: none; }
    iframe { flex: 1 1 auto; width: 100%; border: 0; background: #fff; }
    .empty { margin: 24px 16px; color: #9aa3b2; }
  </style>
</head>
<body>
  <div class="split">
    ${splitPane(left, 'Master ticket')}
    ${splitPane(right, 'External ticket')}
  </div>
</body>
</html>`;
}

/** Open master (left) and external (right) in a new tab, split by a vertical divider. */
export function openSplitTicketView(
  masterHref: string | null | undefined,
  externalHref: string | null | undefined
): boolean {
  const html = splitTicketViewHtml(masterHref, externalHref);
  if (!html || typeof window === 'undefined') return false;
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}
