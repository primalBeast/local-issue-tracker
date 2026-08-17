import { mount } from 'svelte';
import App from './App.svelte';
import {
  applyTheme,
  applyTransparentPanels,
  parseTransparentPanels,
  THEME_STORAGE_KEY,
  TRANSPARENT_PANELS_KEY,
} from './lib/themes';
import './styles/app.css';

try {
  applyTheme(localStorage.getItem(THEME_STORAGE_KEY));
  applyTransparentPanels(parseTransparentPanels(localStorage.getItem(TRANSPARENT_PANELS_KEY)));
} catch {
  applyTheme(null);
  applyTransparentPanels(false);
}

const app = mount(App, { target: document.getElementById('app')! });
export default app;
