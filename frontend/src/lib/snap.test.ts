import { describe, expect, it } from 'vitest';
import { snapToGrid, workspaceGridStep, clampZoom, MIN_PANEL_W, resizeFromEdge } from './snap';

describe('snap', () => {
  it('uses 5px screen grid at zoom 1', () => {
    expect(workspaceGridStep(1)).toBe(5);
    expect(snapToGrid(12, 1)).toBe(10);
    expect(snapToGrid(13, 1)).toBe(15);
  });

  it('adjusts step when zoomed out', () => {
    expect(workspaceGridStep(0.5)).toBe(10);
    expect(snapToGrid(25, 0.5)).toBe(30);
  });

  it('clamps zoom', () => {
    expect(clampZoom(0.001)).toBe(0.02);
    expect(clampZoom(0.1)).toBe(0.1);
    expect(clampZoom(3)).toBe(1.75);
  });

  it('min panel width constant', () => {
    expect(MIN_PANEL_W).toBe(200);
  });

  it('resizes from the east without moving x', () => {
    const next = resizeFromEdge({ x: 40, y: 20, width: 300, height: 200 }, 'e', 25, 0, 1);
    expect(next.x).toBe(40);
    expect(next.width).toBe(325);
  });

  it('resizes from the west and keeps the right edge', () => {
    const orig = { x: 100, y: 20, width: 300, height: 200 };
    const next = resizeFromEdge(orig, 'w', 20, 0, 1);
    expect(next.x + next.width).toBe(orig.x + orig.width);
    expect(next.width).toBe(280);
  });

  it('resizes from the north and keeps the bottom edge', () => {
    const orig = { x: 0, y: 80, width: 300, height: 240 };
    const next = resizeFromEdge(orig, 'n', 0, 30, 1);
    expect(next.y + next.height).toBe(orig.y + orig.height);
    expect(next.height).toBe(210);
  });
});
