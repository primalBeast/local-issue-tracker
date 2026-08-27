import { describe, expect, it } from 'vitest';
import {
  fitView,
  focusView,
  panAfterZoom,
  panelsWorldBounds,
  screenToWorld,
  worldToScreen,
  zoomFromPointerScrub,
  zoomFromWheelDelta,
} from './viewport';

describe('viewport', () => {
  it('round-trips screen and world', () => {
    const pan = { x: 40, y: -20 };
    const world = { x: 100, y: 50 };
    const screen = worldToScreen(pan, 2, world);
    expect(screen).toEqual({ x: 240, y: 80 });
    expect(screenToWorld(pan, 2, screen)).toEqual(world);
  });

  it('zooms out on a positive mouse-wheel delta', () => {
    const next = zoomFromWheelDelta(1, 120, 0);
    expect(next).toBeLessThan(1);
    expect(next).toBeGreaterThan(0.7);
  });

  it('treats line-mode deltas as larger than raw pixels', () => {
    expect(zoomFromWheelDelta(1, 3, 1)).toBeLessThan(zoomFromWheelDelta(1, 3, 0));
  });

  it('zooms in when dragging the readout up or right, out down or left', () => {
    expect(zoomFromPointerScrub(1, 40, 0)).toBeGreaterThan(1);
    expect(zoomFromPointerScrub(1, 0, -40)).toBeGreaterThan(1);
    expect(zoomFromPointerScrub(1, -40, 0)).toBeLessThan(1);
    expect(zoomFromPointerScrub(1, 0, 40)).toBeLessThan(1);
  });

  it('keeps the world point under the pointer when zooming', () => {
    const pan = { x: 10, y: 20 };
    const pointer = { x: 200, y: 150 };
    const oldZ = 1;
    const newZ = 2;
    const worldBefore = screenToWorld(pan, oldZ, pointer);
    const nextPan = panAfterZoom(pan, oldZ, newZ, pointer);
    const worldAfter = screenToWorld(nextPan, newZ, pointer);
    expect(worldAfter.x).toBeCloseTo(worldBefore.x);
    expect(worldAfter.y).toBeCloseTo(worldBefore.y);
  });

  it('computes a union bounds for panels', () => {
    const b = panelsWorldBounds([
      { x: 0, y: 0, width: 100, height: 50 },
      { x: 200, y: 80, width: 40, height: 20 },
    ]);
    expect(b).toEqual({ x: 0, y: 0, width: 240, height: 100 });
  });

  it('fits bounds in the viewport and keeps them on screen', () => {
    const bounds = { x: 0, y: 0, width: 500, height: 250 };
    const view = fitView(bounds, { width: 800, height: 600 }, 0);
    expect(view.zoom).toBeCloseTo(1.6);
    const tl = worldToScreen(view.pan, view.zoom, { x: 0, y: 0 });
    const br = worldToScreen(view.pan, view.zoom, { x: 500, y: 250 });
    expect(tl.x).toBeGreaterThanOrEqual(-0.01);
    expect(tl.y).toBeGreaterThanOrEqual(-0.01);
    expect(br.x).toBeLessThanOrEqual(800.01);
    expect(br.y).toBeLessThanOrEqual(600.01);
  });

  it('centres a focused panel and raises zoom to 100% when zoomed out', () => {
    const bounds = { x: 100, y: 40, width: 200, height: 80 };
    const view = focusView(bounds, { width: 800, height: 600 }, 0.4);
    expect(view.zoom).toBe(1);
    const cx = bounds.x + bounds.width / 2;
    const cy = bounds.y + bounds.height / 2;
    const screenCenter = worldToScreen(view.pan, view.zoom, { x: cx, y: cy });
    expect(screenCenter.x).toBeCloseTo(400);
    expect(screenCenter.y).toBeCloseTo(300);
  });

  it('keeps zoom at or above 100% when focusing', () => {
    const bounds = { x: 100, y: 40, width: 200, height: 80 };
    const view = focusView(bounds, { width: 800, height: 600 }, 1.4);
    expect(view.zoom).toBe(1.4);
    const screenCenter = worldToScreen(view.pan, view.zoom, {
      x: bounds.x + bounds.width / 2,
      y: bounds.y + bounds.height / 2,
    });
    expect(screenCenter.x).toBeCloseTo(400);
    expect(screenCenter.y).toBeCloseTo(300);
  });
});
