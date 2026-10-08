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

describe('project lock source wiring', () => {
  it('window close flushes, then releases, then calls close_app', () => {
    const closeAt = appSource.indexOf('window-chrome-close');
    expect(closeAt).toBeGreaterThanOrEqual(0);
    const closeRegion = appSource.slice(closeAt, closeAt + 450);
    const flushAt = closeRegion.indexOf('flushThen');
    const releaseAt = closeRegion.indexOf('releaseAll');
    const closeAppAt = closeRegion.indexOf('close_app');
    expect(flushAt).toBeGreaterThanOrEqual(0);
    expect(releaseAt).toBeGreaterThan(flushAt);
    expect(closeAppAt).toBeGreaterThan(releaseAt);
  });

  it('reloadApp flushes and never releases', () => {
    const reload = fnBody(appSource, 'reloadApp');
    expect(reload).toContain('await flushThen');
    expect(reload.indexOf('await flushThen')).toBeLessThan(reload.indexOf('location.reload'));
    expect(reload).not.toContain('releaseAll');
    expect(reload).not.toContain('releaseProject');
  });

  it('does not listen for pagehide or beforeunload to release a claim', () => {
    expect(appSource).toContain('installUnloadFlush(');
    expect(appSource).not.toContain('pagehide');
    expect(appSource).not.toContain('beforeunload');
    expect(appSource).not.toContain("addEventListener('visibilitychange'");
    expect(appSource).not.toContain('addEventListener("visibilitychange"');
  });

  it('passes clientId to main_ready and exposes the python closing hooks', () => {
    expect(appSource).toContain('main_ready?.(clientId)');
    expect(appSource).toContain('__litCloseFlush');
    expect(appSource).toContain('__litSavesPending');
    expect(appSource).toContain('main_ready?: (clientId?: string)');
  });

  it('picker buttons use pickerItemState for disabled and title', () => {
    expect(appSource).toContain('pickerItemState(');
    expect(appSource).toContain('disabled={state.disabled}');
    expect(appSource).toContain('title={state.title}');
    expect(appSource).toContain('Close project');
  });

  it('switchProject flushes before it releases the previous project', () => {
    const start = appSource.indexOf('async function switchProject');
    const end = appSource.indexOf('async function createNewProject');
    expect(start).toBeGreaterThanOrEqual(0);
    expect(end).toBeGreaterThan(start);
    const body = appSource.slice(start, end);
    const flushAt = body.indexOf('itemSaveQueue.flush()');
    const workspaceAt = body.indexOf('flushWorkspaceSave()');
    const claimAt = body.indexOf('claimProject(');
    const releaseAt = body.indexOf('releaseProject(');
    const loadAt = body.indexOf('loadProject(');
    expect(flushAt).toBeGreaterThanOrEqual(0);
    expect(workspaceAt).toBeGreaterThan(flushAt);
    expect(claimAt).toBeGreaterThan(workspaceAt);
    expect(releaseAt).toBeGreaterThan(claimAt);
    expect(loadAt).toBeGreaterThan(releaseAt);
  });
});
