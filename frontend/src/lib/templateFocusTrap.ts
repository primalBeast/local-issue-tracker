export const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

export function wrapFocusIndex(count: number, current: number, shift: boolean): number {
  if (count <= 0) return 0;
  if (shift) return current <= 0 ? count - 1 : current - 1;
  return current >= count - 1 ? 0 : current + 1;
}

export function isShown(el: HTMLElement): boolean {
  return el.getClientRects().length > 0;
}

export function focusableIn(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)].filter((el) => {
    if (el.closest('[hidden], [aria-hidden="true"]')) return false;
    return isShown(el);
  });
}

export function handleFocusTrap(root: HTMLElement, e: KeyboardEvent): void {
  if (e.key !== 'Tab') return;
  const nodes = focusableIn(root);
  if (!nodes.length) {
    e.preventDefault();
    root.focus();
    return;
  }
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  const active = document.activeElement;
  if (e.shiftKey) {
    if (active === first || !root.contains(active)) {
      e.preventDefault();
      last.focus();
    }
  } else if (active === last || !root.contains(active)) {
    e.preventDefault();
    first.focus();
  }
}

export function restoreFocus(opener: Element | null): void {
  if (opener instanceof HTMLElement && document.contains(opener)) opener.focus();
}
