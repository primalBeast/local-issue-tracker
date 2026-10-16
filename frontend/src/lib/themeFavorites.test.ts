import { describe, expect, it } from 'vitest';
import { THEME_MENU } from './themes';
import {
  favoritePulsePeriod,
  parseFavorites,
  themeMenuRows,
  themeNavIds,
  toggleFavorite,
} from './themeFavorites';

describe('theme favourites', () => {
  it('picks a cycle whose bright-to-dark half is about two seconds', () => {
    expect(favoritePulsePeriod(() => 0)).toBe(3.4);
    expect(favoritePulsePeriod(() => 0.999)).toBe(4.6);
  });

  it('toggles a theme and keeps the pulse it was given', () => {
    const once = toggleFavorite([], 'midnight', () => 0.5);
    expect(once).toEqual([{ id: 'midnight', pulse: 4 }]);
    expect(toggleFavorite(once, 'midnight')).toEqual([]);
  });

  it('drops junk and duplicate ids', () => {
    expect(
      parseFavorites([
        { id: 'midnight', pulse: 4.2 },
        { id: 'midnight', pulse: 3 },
        { id: '../nope', pulse: 4 },
        { id: 'aurora', pulse: 99 },
        'nope',
      ])
    ).toEqual([
      { id: 'midnight', pulse: 4.2 },
      { id: 'aurora', pulse: 8 },
    ]);
  });

  it('lists favourites first and still leaves them in their own group', () => {
    const favs = [{ id: THEME_MENU[3].theme.id, pulse: 4 }];
    const rows = themeMenuRows(THEME_MENU, favs);
    expect(rows[0].group).toBe('Favourites');
    expect(rows[0].theme.id).toBe(favs[0].id);
    expect(rows.filter((row) => row.theme.id === favs[0].id)).toHaveLength(2);
    expect(rows.some((row) => row.group !== 'Favourites' && row.theme.id === favs[0].id)).toBe(true);
  });

  it('walks favourites, then the other themes, without repeating an id', () => {
    const id = THEME_MENU[2].theme.id;
    const ids = themeNavIds(THEME_MENU, [{ id, pulse: 4 }]);
    expect(ids[0]).toBe(id);
    expect(ids.filter((item) => item === id)).toHaveLength(1);
    expect(new Set(ids).size).toBe(THEME_MENU.length);
  });
});
