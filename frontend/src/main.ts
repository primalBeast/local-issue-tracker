import { mount } from 'svelte';
import App from './App.svelte';
import {
  applyPanelTransparency,
  applyTheme,
  applyTransparentPanels,
  parseTransparencyMap,
  parseTransparentPanels,
  THEME_STORAGE_KEY,
  TRANSPARENCY_BY_THEME_KEY,
  TRANSPARENT_PANELS_KEY,
  transparencyForTheme,
} from './lib/themes';
import './styles/app.css';

try {
  const theme = applyTheme(localStorage.getItem(THEME_STORAGE_KEY));
  applyTransparentPanels(parseTransparentPanels(localStorage.getItem(TRANSPARENT_PANELS_KEY)));
  const map = parseTransparencyMap(JSON.parse(localStorage.getItem(TRANSPARENCY_BY_THEME_KEY) || '{}'));
  applyPanelTransparency(transparencyForTheme(theme.id, map));
} catch {
  applyTheme(null);
  applyTransparentPanels(false);
  applyPanelTransparency(1);
}

const app = mount(App, { target: document.getElementById('app')! });
export default app;
