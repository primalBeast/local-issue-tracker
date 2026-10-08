import { describe, expect, it } from 'vitest';
import appSource from '../App.svelte?raw';

function fnBody(source: string, name: string): string {
  const marker = `function ${name}`;
  const start = source.indexOf(marker);
  expect(start, name).toBeGreaterThanOrEqual(0);
  const lineStart = source.lastIndexOf('\n', start) + 1;
  const next = source.indexOf('\n  function ', start + marker.length);
  return source.slice(lineStart, next === -1 ? undefined : next);
}

describe('autosave source wiring', () => {
  it('wires flushThen, unload flush, and drag hold/release, and drops the old per-item patch timer', () => {
    const closeAt = appSource.indexOf('window-chrome-close');
    expect(closeAt).toBeGreaterThanOrEqual(0);
    const closeRegion = appSource.slice(closeAt, closeAt + 450);
    expect(closeRegion).toContain('flushThen');
    expect(closeRegion.indexOf('flushThen')).toBeLessThan(closeRegion.indexOf('close_app'));

    const reload = fnBody(appSource, 'reloadApp');
    expect(reload).toContain('async function reloadApp');
    expect(reload).toContain('await flushThen');
    expect(reload.indexOf('await flushThen')).toBeLessThan(reload.indexOf('location.reload'));

    const f5 = appSource.indexOf("e.key === 'F5'");
    expect(f5).toBeGreaterThanOrEqual(0);
    const f5Branch = appSource.slice(f5, appSource.indexOf("e.key === 'Escape'", f5));
    expect(f5Branch).toContain('stopImmediatePropagation');
    expect(f5Branch).toContain('reloadApp()');

    expect(appSource).toContain('installUnloadFlush(');

    const pointerDown = fnBody(appSource, 'onUrgencyPointerDown');
    const endDrag = fnBody(appSource, 'endUrgencyDrag');
    expect(pointerDown).toContain('.hold()');
    expect(endDrag).toContain('.release()');

    expect(appSource).not.toContain('api.patchItem(project!.slug');
    expect(appSource).not.toContain('itemSaveTimers');
  });
});
