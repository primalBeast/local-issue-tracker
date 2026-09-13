import { describe, expect, it } from 'vitest';
import {
  dimScale,
  FOCUS_HIT_PAD_PX,
  FOCUS_PANEL_ZOOM,
  FOCUS_TOP_RATIO,
  FOCUS_TOP_RATIO_MIN,
  OTHER_PANELS_ZOOM,
  focusStageCamera,
  focusTopPx,
  inPaddedRect,
} from './focusStage';
import { worldToScreen } from './viewport';

describe('focusStageCamera', () => {
  const panel = { x: 100, y: 40, width: 200, height: 80 };
  const viewport = { width: 800, height: 600 };

  it('zooms the focused panel to 110% of the previous zoom when already at 100%+', () => {
    const view = focusStageCamera(panel, viewport, 1);
    expect(view.zoom).toBeCloseTo(FOCUS_PANEL_ZOOM);
    const from140 = focusStageCamera(panel, viewport, 1.4);
    expect(from140.zoom).toBeCloseTo(1.4 * FOCUS_PANEL_ZOOM);
  });

  it('raises a zoomed-out board to 100% instead of 110%', () => {
    const view = focusStageCamera(panel, viewport, 0.4);
    expect(view.zoom).toBe(1);
  });

  it('places the focused panel top 10% down from the viewport top', () => {
    const view = focusStageCamera(panel, viewport, 1);
    const top = worldToScreen(view.pan, view.zoom, { x: panel.x, y: panel.y });
    expect(top.y).toBeCloseTo(viewport.height * FOCUS_TOP_RATIO);
  });

  it('keeps the focused panel horizontally centred', () => {
    const view = focusStageCamera(panel, viewport, 1);
    const mid = worldToScreen(view.pan, view.zoom, {
      x: panel.x + panel.width / 2,
      y: panel.y,
    });
    expect(mid.x).toBeCloseTo(viewport.width / 2);
  });

  it('scales other panels to 80% of the (floored) base zoom', () => {
    expect(dimScale(1, FOCUS_PANEL_ZOOM)).toBeCloseTo(OTHER_PANELS_ZOOM / FOCUS_PANEL_ZOOM);
    expect(dimScale(0.4, 1)).toBeCloseTo(OTHER_PANELS_ZOOM);
  });

  it('raises a tall panel so the bottom gap is not smaller than the top gap', () => {
    const tall = { ...panel, height: 520 };
    const view = focusStageCamera(tall, viewport, 1);
    const top = worldToScreen(view.pan, view.zoom, { x: tall.x, y: tall.y });
    const bottom = worldToScreen(view.pan, view.zoom, { x: tall.x, y: tall.y + tall.height });
    const topGap = top.y;
    const bottomGap = viewport.height - bottom.y;
    expect(topGap).toBeLessThan(viewport.height * FOCUS_TOP_RATIO);
    expect(topGap).toBeGreaterThanOrEqual(viewport.height * FOCUS_TOP_RATIO_MIN - 0.01);
    expect(bottomGap).toBeCloseTo(topGap);
  });

  it('treats a 20px ring around the panel as inside the focus hit area', () => {
    const r = { left: 100, top: 80, right: 300, bottom: 200 };
    expect(inPaddedRect(100, 80, r, FOCUS_HIT_PAD_PX)).toBe(true);
    expect(inPaddedRect(90, 80, r, FOCUS_HIT_PAD_PX)).toBe(true);
    expect(inPaddedRect(79, 80, r, FOCUS_HIT_PAD_PX)).toBe(false);
    expect(inPaddedRect(200, 220, r, FOCUS_HIT_PAD_PX)).toBe(true);
    expect(inPaddedRect(200, 221, r, FOCUS_HIT_PAD_PX)).toBe(false);
  });

  it('does not put the top closer than 1% of the viewport', () => {
    expect(focusTopPx(1000, 990)).toBeCloseTo(10);
    const huge = { ...panel, height: 2000 };
    const view = focusStageCamera(huge, viewport, 1);
    const top = worldToScreen(view.pan, view.zoom, { x: huge.x, y: huge.y });
    expect(top.y).toBeCloseTo(viewport.height * FOCUS_TOP_RATIO_MIN);
  });
});
