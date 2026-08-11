import { describe, expect, it } from 'vitest';
import { snapToGrid, workspaceGridStep, clampZoom, MIN_PANEL_W } from './snap';

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
    expect(clampZoom(0.1)).toBe(0.35);
    expect(clampZoom(3)).toBe(1.75);
  });

  it('min panel width constant', () => {
    expect(MIN_PANEL_W).toBe(200);
  });
});
