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
