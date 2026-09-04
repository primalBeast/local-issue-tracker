export const ASSIGNED_FIELD_IDS = ['dn_assigned_to', 'customer_assigned_to'] as const;

export function isAssignedField(id: string): boolean {
  return (ASSIGNED_FIELD_IDS as readonly string[]).includes(id);
}

/** True when `name` is already in the field's saved list, ignoring case and trim. */
export function nameAlreadyListed(options: string[] | undefined, name: string): boolean {
  const n = name.trim().toLowerCase();
  if (!n) return false;
  return (options ?? []).some((o) => o.trim().toLowerCase() === n);
}
