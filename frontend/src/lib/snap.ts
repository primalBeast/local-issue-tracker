/** 5px screen-pixel grid; workspace step = 5 / zoom */

export const SCREEN_GRID_PX = 5;
export const MIN_PANEL_W = 200;
export const MIN_PANEL_H = 120;
/** Safety floor only — do not treat this as a UX zoom-out limit. */
export const ZOOM_MIN = 0.02;
export const ZOOM_MAX = 1.75;

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function workspaceGridStep(zoom: number): number {
  const z = zoom <= 0 ? 1 : zoom;
  return SCREEN_GRID_PX / z;
}

export function snapToGrid(value: number, zoom: number): number {
  const step = workspaceGridStep(zoom);
  return Math.round(value / step) * step;
}

export function snapSize(width: number, height: number, zoom: number): { width: number; height: number } {
  return {
    width: Math.max(MIN_PANEL_W, snapToGrid(width, zoom)),
    height: Math.max(MIN_PANEL_H, snapToGrid(height, zoom)),
  };
}

export function clampZoom(zoom: number): number {
  return clamp(zoom, ZOOM_MIN, ZOOM_MAX);
}

export type ResizeEdge = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

export function resizeCursor(edge: ResizeEdge): string {
  if (edge === 'n' || edge === 's') return 'ns-resize';
  if (edge === 'e' || edge === 'w') return 'ew-resize';
  if (edge === 'ne' || edge === 'sw') return 'nesw-resize';
  return 'nwse-resize';
}

/** Resize a panel from an edge/corner. Opposite edges stay put; size is snapped and clamped. */
export function resizeFromEdge(
  orig: { x: number; y: number; width: number; height: number },
  edge: ResizeEdge,
  dx: number,
  dy: number,
  zoom: number
): { x: number; y: number; width: number; height: number } {
  let left = orig.x;
  let top = orig.y;
  let right = orig.x + orig.width;
  let bottom = orig.y + orig.height;

  if (edge.includes('e')) right = snapToGrid(orig.x + orig.width + dx, zoom);
  if (edge.includes('w')) left = snapToGrid(orig.x + dx, zoom);
  if (edge.includes('s')) bottom = snapToGrid(orig.y + orig.height + dy, zoom);
  if (edge.includes('n')) top = snapToGrid(orig.y + dy, zoom);

  if (right - left < MIN_PANEL_W) {
    if (edge.includes('w')) left = right - MIN_PANEL_W;
    else right = left + MIN_PANEL_W;
  }
  if (bottom - top < MIN_PANEL_H) {
    if (edge.includes('n')) top = bottom - MIN_PANEL_H;
    else bottom = top + MIN_PANEL_H;
  }

  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  };
}
