/** Infinite-canvas pan + zoom helpers. Screen = pan + world * zoom. */

export type Point = { x: number; y: number };

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
