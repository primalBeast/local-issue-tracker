function asClosestHost(target: EventTarget | null): { closest: (sel: string) => { getAttribute?: (n: string) => string | null; querySelector?: (sel: string) => { textContent?: string | null } | null } | null } | null {
  if (!target || typeof target !== 'object') return null;
  const el = target as { closest?: unknown };
  if (typeof el.closest !== 'function') return null;
  return target as unknown as {
    closest: (
      sel: string
    ) => {
      getAttribute?: (n: string) => string | null;
      querySelector?: (sel: string) => { textContent?: string | null } | null;
    } | null;
  };
}

export function fieldIdFromTarget(target: EventTarget | null): string | null {
  const el = asClosestHost(target);
  const hit = el?.closest?.('[data-field-id]');
  const id = hit?.getAttribute?.('data-field-id');
  return id || null;
}

export function selectField(current: string | null, id: string | null): string | null {
  if (!id) return current;
  return id;
}

export function isSelected(selectedId: string | null, fieldId: string): boolean {
  return Boolean(selectedId) && selectedId === fieldId;
}

const TITLE_BAR_PREVIEW_ID = 'ticket_key';
const TITLE_BAR_FIELD_IDS = new Set(['ticket_key', 'title', 'alternate_ticket']);

/** Preview hit id for a field. Title-bar fields share one hit. */
export function previewScrollId(fieldId: string): string {
  return TITLE_BAR_FIELD_IDS.has(fieldId) ? TITLE_BAR_PREVIEW_ID : fieldId;
}

/** Scroll the other pane when selection moves between the canvas and the preview. */
export function scrollCounterpartIntoView(
  root: ParentNode | null,
  origin: 'canvas' | 'preview',
  id: string
): void {
  if (!root || !id) return;
  const wantPreview = origin === 'canvas';
  const selector = wantPreview ? '.template-preview-hit' : '.template-chip';
  const lookup = wantPreview ? previewScrollId(id) : id;
  for (const node of root.querySelectorAll<HTMLElement>(selector)) {
    if ((node.dataset?.fieldId || '') !== lookup) continue;
    node.scrollIntoView({ block: 'nearest' });
    return;
  }
}

export function nextSelectionAfterRemove(fields: { id: string }[], removedId: string, current: string | null): string | null {
  if (current !== removedId) {
    return fields.some((f) => f.id === current) ? current : (fields[0]?.id ?? null);
  }
  const i = fields.findIndex((f) => f.id === removedId);
  const remaining = fields.filter((f) => f.id !== removedId);
  if (!remaining.length) return null;
  return remaining[Math.min(i, remaining.length - 1)]?.id ?? remaining[0].id;
}

export function fieldIdFromTitleBarClick(
  target: EventTarget | null,
  labels: { ticket: string; title: string; alternate: string }
): string {
  const el = asClosestHost(target);
  const label = el?.closest('label')?.querySelector?.('.field-label')?.textContent?.trim();
  if (label === labels.title) return 'title';
  if (label === labels.alternate) return 'alternate_ticket';
  if (label === labels.ticket) return 'ticket_key';
  return 'ticket_key';
}
