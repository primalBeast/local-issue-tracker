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
