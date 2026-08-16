import { describe, expect, it } from 'vitest';
import { panAfterZoom, screenToWorld, worldToScreen } from './viewport';

describe('viewport', () => {
  it('round-trips screen and world', () => {
    const pan = { x: 40, y: -20 };
    const world = { x: 100, y: 50 };
    const screen = worldToScreen(pan, 2, world);
    expect(screen).toEqual({ x: 240, y: 80 });
    expect(screenToWorld(pan, 2, screen)).toEqual(world);
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
});
