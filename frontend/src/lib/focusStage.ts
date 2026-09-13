/** Staged Focus: zoom the chosen panel, shrink+blur the rest, restore on click-outside.
 *
 * Set `FOCUS_STAGE_ENABLED` to `false` to go back to the old Focus behaviour
 * (centre the panel, raise zoom to at least 100%, no blur).
 */
export const FOCUS_STAGE_ENABLED = true;

export const FOCUS_PANEL_ZOOM = 1.1;
export const OTHER_PANELS_ZOOM = 0.8;
export const FOCUS_TOP_RATIO = 0.1;
export const FOCUS_TOP_RATIO_MIN = 0.01;
export const FOCUS_TRANSITION_MS = 180;
/** Extra screen pixels around the focused panel that do not end Focus. */
export const FOCUS_HIT_PAD_PX = 20;
/** CSS blur on non-focused panels (~20% of a 20px blur). */
export const OTHER_PANEL_BLUR = '4px';

export type FocusStage = {
  panelId: string;
  prevZoom: number;
  prevPan: { x: number; y: number };
  zoom: number;
  pan: { x: number; y: number };
};

function saneZoom(prevZoom: number): number {
  return Number.isFinite(prevZoom) && prevZoom > 0 ? prevZoom : 1;
}

/** Floor below-100% zoom to 100% before staging. */
export function focusBaseZoom(prevZoom: number): number {
  const z = saneZoom(prevZoom);
  return z < 1 ? 1 : z;
}

export function focusCanvasZoom(prevZoom: number): number {
  const z = saneZoom(prevZoom);
  return z < 1 ? 1 : z * FOCUS_PANEL_ZOOM;
}

export function dimScale(prevZoom: number, canvasZoom: number): number {
  const other = focusBaseZoom(prevZoom) * OTHER_PANELS_ZOOM;
  return canvasZoom > 0 ? other / canvasZoom : OTHER_PANELS_ZOOM / FOCUS_PANEL_ZOOM;
}

/** Top padding in px: prefer 10% of the viewport; if the panel would leave a
 * smaller gap below than above, raise it (down to 1% from the top). */
export function focusTopPx(viewportHeight: number, panelScreenHeight: number): number {
  const vh = Math.max(1, viewportHeight);
  const h = Math.max(0, panelScreenHeight);
  const preferred = vh * FOCUS_TOP_RATIO;
  const minTop = vh * FOCUS_TOP_RATIO_MIN;
  const bottomGap = vh - preferred - h;
  if (bottomGap >= preferred) return preferred;
  return Math.min(preferred, Math.max(minTop, (vh - h) / 2));
}

export function inPaddedRect(
  x: number,
  y: number,
  r: { left: number; top: number; right: number; bottom: number },
  pad: number
): boolean {
  return x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad;
}

export function focusStageCamera(
  panel: { x: number; y: number; width: number; height: number },
  viewport: { width: number; height: number },
  prevZoom: number
): { zoom: number; pan: { x: number; y: number } } {
  const zoom = focusCanvasZoom(prevZoom);
  const vw = Math.max(1, viewport.width);
  const vh = Math.max(1, viewport.height);
  const width = Math.max(0, panel.width);
  const height = Math.max(0, panel.height);
  const top = focusTopPx(vh, height * zoom);
  return {
    zoom,
    pan: {
      x: vw / 2 - (panel.x + width / 2) * zoom,
      y: top - panel.y * zoom,
    },
  };
}
