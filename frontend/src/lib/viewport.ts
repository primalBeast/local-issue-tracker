/** Infinite-canvas pan + zoom helpers. Screen = pan + world * zoom. */

import { clamp, ZOOM_MAX, ZOOM_MIN } from './snap';

export type Point = { x: number; y: number };
export type Rect = { x: number; y: number; width: number; height: number };

export const FIT_PADDING_PX = 48;
/** Focus never zooms in past this, even if the panel would still fit. */
export const FOCUS_ZOOM_MAX = 1.25;

export function defaultPan(): Point {
  return { x: 0, y: 0 };
}

export function screenToWorld(pan: Point, zoom: number, screen: Point): Point {
  const z = zoom <= 0 ? 1 : zoom;
  return {
    x: (screen.x - pan.x) / z,
    y: (screen.y - pan.y) / z,
  };
}

export function worldToScreen(pan: Point, zoom: number, world: Point): Point {
  const z = zoom <= 0 ? 1 : zoom;
  return {
    x: pan.x + world.x * z,
    y: pan.y + world.y * z,
  };
}

/** Keep the world point under `pointer` (viewport-local) fixed while zoom changes. */
export function panAfterZoom(pan: Point, oldZoom: number, newZoom: number, pointer: Point): Point {
  const world = screenToWorld(pan, oldZoom, pointer);
  return {
    x: pointer.x - world.x * newZoom,
    y: pointer.y - world.y * newZoom,
  };
}

/** Normalize wheel delta (pixels / lines / pages) into a new zoom factor. */
export function zoomFromWheelDelta(oldZoom: number, deltaY: number, deltaMode = 0): number {
  let dy = deltaY;
  if (deltaMode === 1) dy *= 16;
  if (deltaMode === 2) dy *= 800;
  return oldZoom * Math.exp(-dy * 0.0015);
}

/** Drag on the zoom readout: right and up zoom in, left and down zoom out. */
export function zoomFromPointerScrub(startZoom: number, dx: number, dy: number): number {
  return startZoom * Math.exp((dx - dy) * 0.008);
}

export function panelsWorldBounds(
  panels: Array<{ x: number; y: number; width: number; height: number }>
): Rect | null {
  if (!panels.length) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of panels) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x + Math.max(0, p.width));
    maxY = Math.max(maxY, p.y + Math.max(0, p.height));
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

/** Zoom and pan so `bounds` is centered and fully visible in the viewport. */
export function fitView(
  bounds: Rect,
  viewport: { width: number; height: number },
  padding = FIT_PADDING_PX,
  maxZoom = ZOOM_MAX
): { zoom: number; pan: Point } {
  const vw = Math.max(1, viewport.width);
  const vh = Math.max(1, viewport.height);
  const innerW = Math.max(1, vw - padding * 2);
  const innerH = Math.max(1, vh - padding * 2);
  const bw = Math.max(1, bounds.width);
  const bh = Math.max(1, bounds.height);
  const zoom = clamp(Math.min(innerW / bw, innerH / bh), ZOOM_MIN, maxZoom);
  const cx = bounds.x + bounds.width / 2;
  const cy = bounds.y + bounds.height / 2;
  return {
    zoom,
    pan: {
      x: vw / 2 - cx * zoom,
      y: vh / 2 - cy * zoom,
    },
  };
}

/** Fit a panel for Focus: centre it, and never zoom in past 125%. */
export function focusView(
  bounds: Rect,
  viewport: { width: number; height: number },
  padding = FIT_PADDING_PX
): { zoom: number; pan: Point } {
  return fitView(bounds, viewport, padding, FOCUS_ZOOM_MAX);
}
