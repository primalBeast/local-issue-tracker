import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  appearanceFromWorkspace,
  clampTransparency,
  parseTransparencyMap,
  parseTransparentPanels,
  resolveTheme,
  THEME_GROUPS,
  THEME_MENU,
  THEMES,
  transparencyForTheme,
} from './themes';

const here = dirname(fileURLToPath(import.meta.url));

describe('themes', () => {
  it('includes the midnight default plus one hundred and fifty-one wallpapers', () => {
    expect(THEMES[0].id).toBe('midnight');
    expect(THEMES[0].name.toLowerCase()).toContain('default');
    expect(THEMES).toHaveLength(152);
    expect(THEMES.filter((t) => t.wallpaper)).toHaveLength(151);
  });

  it('groups every look into the theme menu without duplicates', () => {
    const grouped = THEME_GROUPS.flatMap((g) => g.ids);
    expect(grouped).toHaveLength(THEMES.length);
    expect(new Set(grouped).size).toBe(THEMES.length);
    expect(THEME_MENU).toHaveLength(THEMES.length);
    const ids = new Set(THEMES.map((t) => t.id));
    for (const id of grouped) expect(ids.has(id), `unknown grouped id ${id}`).toBe(true);
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
    expect(appearanceFromWorkspace({ transparent_panels: false }, 'iris', true)).toEqual({
      theme: 'iris',
      transparent: false,
    });
  });

  it('clamps and looks up per-theme transparency', () => {
    expect(clampTransparency(0.4)).toBe(0.4);
    expect(clampTransparency(-2)).toBe(0);
    expect(clampTransparency(3)).toBe(1);
    expect(clampTransparency('nope')).toBe(0.66);
    const map = parseTransparencyMap({ aurora: 0.25, dark: 0.8, junk: 'x' });
    expect(map.aurora).toBe(0.25);
    expect(map.midnight).toBe(0.8);
    expect(transparencyForTheme('ember', map)).toBe(0.66);
    expect(transparencyForTheme('aurora', map)).toBe(0.25);
  });
});
