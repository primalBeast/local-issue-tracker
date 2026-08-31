/** External-ticket URL slots. Remove with UrlTicketField + fields.json entries to back out. */
export const EXTERNAL_TICKET_IDS = [
  'external_ticket',
  'external_ticket_2',
  'external_ticket_3',
] as const;

export function isExternalTicketId(id: string): boolean {
  return (EXTERNAL_TICKET_IDS as readonly string[]).includes(id);
}

/** Last path segment after `/` or `\\`. */
export function urlTail(raw: string | null | undefined): string {
  const s = String(raw ?? '').trim().replace(/[/\\]+$/, '');
  if (!s) return '';
  const i = Math.max(s.lastIndexOf('/'), s.lastIndexOf('\\'));
  return i >= 0 ? s.slice(i + 1) : s;
}

export function filledTicketSlots(fields: Record<string, unknown>): number {
  let n = 1;
  if (String(fields.external_ticket_2 ?? '').trim()) n = 2;
  if (String(fields.external_ticket_3 ?? '').trim()) n = 3;
  return n;
}

export function slotsToShow(
  revealed: number | undefined,
  fields: Record<string, unknown>
): number {
  return Math.min(EXTERNAL_TICKET_IDS.length, Math.max(revealed ?? 1, filledTicketSlots(fields)));
}
