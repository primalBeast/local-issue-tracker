import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { appearanceFromWorkspace, parseTransparentPanels, resolveTheme, THEMES } from './themes';

const here = dirname(fileURLToPath(import.meta.url));

describe('themes', () => {
  it('includes the midnight default plus ten wallpapers', () => {
    expect(THEMES[0].id).toBe('midnight');
    expect(THEMES[0].name.toLowerCase()).toContain('default');
    expect(THEMES).toHaveLength(11);
    expect(THEMES.filter((t) => t.wallpaper)).toHaveLength(10);
  });

  it('maps the legacy dark setting to midnight', () => {
    expect(resolveTheme('dark').id).toBe('midnight');
    expect(resolveTheme('default').id).toBe('midnight');
    expect(resolveTheme('aurora').id).toBe('aurora');
    expect(resolveTheme('nope').id).toBe('midnight');
  });

  it('ships a public wallpaper for each themed look', () => {
    for (const t of THEMES) {
      if (!t.wallpaper) continue;
      const file = resolve(here, '../../public', t.wallpaper.replace(/^\//, ''));
      expect(existsSync(file), `missing ${file}`).toBe(true);
      expect(t.vars['--wallpaper']).toContain(t.wallpaper);
      expect(t.vars['--glass-blur']).not.toBe('0px');
    }
  });

  it('keeps midnight opaque with no wallpaper', () => {
    expect(THEMES[0].vars['--wallpaper']).toBe('none');
    expect(THEMES[0].vars['--glass-blur']).toBe('0px');
    expect(THEMES[0].vars['--panel-glass']).toBe('#161a22');
  });

  it('parses the transparent-panels flag', () => {
    expect(parseTransparentPanels(true)).toBe(true);
    expect(parseTransparentPanels('1')).toBe(true);
    expect(parseTransparentPanels('true')).toBe(true);
    expect(parseTransparentPanels(false)).toBe(false);
    expect(parseTransparentPanels('0')).toBe(false);
    expect(parseTransparentPanels(undefined)).toBe(false);
  });

  it('reads a board theme and falls back when the board has none', () => {
    expect(appearanceFromWorkspace({ theme: 'ember', transparent_panels: true }, 'aurora', false)).toEqual({
      theme: 'ember',
      transparent: true,
    });
    expect(appearanceFromWorkspace({ theme: 'dark' }, 'aurora', true)).toEqual({
      theme: 'midnight',
      transparent: true,
    });
    expect(appearanceFromWorkspace({}, 'sakura', false)).toEqual({
      theme: 'sakura',
      transparent: false,
    });
    expect(appearanceFromWorkspace({ transparent_panels: false }, 'neon', true)).toEqual({
      theme: 'neon',
      transparent: false,
    });
  });
});
