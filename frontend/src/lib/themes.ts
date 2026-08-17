export type ThemeId =
  | 'midnight'
  | 'aurora'
  | 'ember'
  | 'abyss'
  | 'lunar'
  | 'sakura'
  | 'solar'
  | 'neon'
  | 'glacier'
  | 'copper'
  | 'nebula';

export type Theme = {
  id: ThemeId;
  name: string;
  wallpaper?: string;
  vars: Record<string, string>;
};

export const THEME_STORAGE_KEY = 'lit:theme';
export const TRANSPARENT_PANELS_KEY = 'lit:transparent-panels';

const MIDNIGHT_VARS: Record<string, string> = {
  '--bg': '#0b0d12',
  '--bg-elevated': '#12151c',
  '--bg-panel': '#161a22',
  '--bg-panel-2': '#1c212c',
  '--bg-input': '#0e1219',
  '--bg-hover': '#232937',
  '--bg-chrome': '#12151c',
  '--bg-sidebar': '#0d1016',
  '--border': '#2a3140',
  '--border-strong': '#3a4458',
  '--text': '#e8eaed',
  '--text-muted': '#9aa3b2',
  '--text-faint': '#6b7385',
  '--accent': '#6ea8fe',
  '--accent-2': '#8b5cf6',
  '--danger': '#f87171',
  '--success': '#4ade80',
  '--warning': '#fbbf24',
  '--shadow': '0 12px 40px rgba(0, 0, 0, 0.45)',
  '--primary-from': '#4f7cff',
  '--primary-to': '#3b6cf0',
  '--primary-border': '#5b7fff',
  '--focus-ring': 'rgba(110, 168, 254, 0.15)',
  '--accent-soft': 'rgba(110, 168, 254, 0.12)',
  '--brand-glow': 'rgba(110, 168, 254, 0.35)',
  '--panel-glass': '#161a22',
  '--chrome-glass': '#12151c',
  '--sidebar-glass': '#0d1016',
  '--canvas-glow-1': 'radial-gradient(1200px 600px at 10% -10%, rgba(110, 168, 254, 0.08), transparent 50%)',
  '--canvas-glow-2': 'radial-gradient(900px 500px at 100% 0%, rgba(139, 92, 246, 0.07), transparent 45%)',
  '--wallpaper': 'none',
  '--wallpaper-veil': 'none',
  '--grid-dot': 'rgba(255, 255, 255, 0.07)',
  '--glass-blur': '0px',
  '--glass-saturate': '1',
};

function themed(
  id: ThemeId,
  name: string,
  file: string,
  accent: string,
  accent2: string,
  extras: Record<string, string>
): Theme {
  const vars: Record<string, string> = {
    ...MIDNIGHT_VARS,
    '--accent': accent,
    '--accent-2': accent2,
    '--primary-from': accent,
    '--primary-to': accent2,
    '--primary-border': accent,
    '--focus-ring': extras['--focus-ring'] ?? 'rgba(255,255,255,0.12)',
    '--accent-soft': extras['--accent-soft'] ?? 'rgba(255,255,255,0.08)',
    '--brand-glow': extras['--brand-glow'] ?? 'rgba(255,255,255,0.25)',
    '--panel-glass': extras['--panel-glass'] ?? 'rgba(12, 14, 20, 0.58)',
    '--chrome-glass': extras['--chrome-glass'] ?? 'rgba(10, 12, 18, 0.52)',
    '--sidebar-glass': extras['--sidebar-glass'] ?? 'rgba(8, 10, 16, 0.48)',
    '--bg-input': extras['--bg-input'] ?? 'rgba(6, 8, 14, 0.48)',
    '--bg-hover': extras['--bg-hover'] ?? 'rgba(255,255,255,0.1)',
    '--bg-panel-2': extras['--bg-panel-2'] ?? 'rgba(255,255,255,0.08)',
    '--border': extras['--border'] ?? 'rgba(255,255,255,0.16)',
    '--border-strong': extras['--border-strong'] ?? 'rgba(255,255,255,0.3)',
    '--shadow': extras['--shadow'] ?? '0 18px 56px rgba(0, 0, 0, 0.48)',
    '--wallpaper': `url(/themes/${file})`,
    '--wallpaper-veil':
      extras['--wallpaper-veil'] ??
      'linear-gradient(180deg, rgba(6,8,14,0.55) 0%, rgba(6,8,14,0.22) 42%, rgba(6,8,14,0.5) 100%)',
    '--canvas-glow-1': extras['--canvas-glow-1'] ?? 'none',
    '--canvas-glow-2': extras['--canvas-glow-2'] ?? 'none',
    '--glass-blur': extras['--glass-blur'] ?? '22px',
    '--glass-saturate': extras['--glass-saturate'] ?? '1.55',
    ...extras,
  };
  vars['--bg-panel'] = vars['--panel-glass'];
  vars['--bg-chrome'] = vars['--chrome-glass'];
  vars['--bg-sidebar'] = vars['--sidebar-glass'];
  vars['--bg-elevated'] = vars['--chrome-glass'];
  return { id, name, wallpaper: `/themes/${file}`, vars };
}

export const THEMES: Theme[] = [
  { id: 'midnight', name: 'Midnight (default)', vars: { ...MIDNIGHT_VARS } },
  themed('aurora', 'Aurora Veil', 'aurora.jpg', '#5eead4', '#a78bfa', {
    '--text': '#e8fffb',
    '--focus-ring': 'rgba(94, 234, 212, 0.22)',
    '--accent-soft': 'rgba(94, 234, 212, 0.14)',
    '--brand-glow': 'rgba(167, 139, 250, 0.45)',
    '--panel-glass': 'rgba(8, 18, 24, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,12,16,0.5) 0%, rgba(4,12,16,0.22) 45%, rgba(6,10,20,0.48) 100%)',
  }),
  themed('ember', 'Ember Observatory', 'ember.jpg', '#fbbf24', '#f43f5e', {
    '--text': '#fff4e6',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(244, 63, 94, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(22, 10, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(18,6,4,0.52) 0%, rgba(18,6,4,0.2) 42%, rgba(10,6,8,0.5) 100%)',
  }),
  themed('abyss', 'Abyssal Jade', 'abyss.jpg', '#22d3ee', '#34d399', {
    '--text': '#e6fffb',
    '--focus-ring': 'rgba(34, 211, 238, 0.22)',
    '--accent-soft': 'rgba(52, 211, 153, 0.14)',
    '--brand-glow': 'rgba(34, 211, 238, 0.4)',
    '--panel-glass': 'rgba(4, 14, 22, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,8,16,0.58) 0%, rgba(2,8,16,0.28) 40%, rgba(2,10,18,0.55) 100%)',
  }),
  themed('lunar', 'Lunar Silk', 'lunar.jpg', '#cbd5e1', '#93c5fd', {
    '--text': '#f8fafc',
    '--text-muted': '#cbd5e1',
    '--focus-ring': 'rgba(203, 213, 225, 0.2)',
    '--accent-soft': 'rgba(147, 197, 253, 0.16)',
    '--brand-glow': 'rgba(226, 232, 240, 0.35)',
    '--panel-glass': 'rgba(12, 16, 24, 0.55)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,10,16,0.48) 0%, rgba(8,10,16,0.18) 45%, rgba(8,10,18,0.46) 100%)',
  }),
  themed('sakura', 'Sakura Noir', 'sakura.jpg', '#fb7185', '#f472b6', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(244, 114, 182, 0.16)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(18, 8, 14, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(12,4,10,0.55) 0%, rgba(12,4,10,0.22) 42%, rgba(10,4,12,0.52) 100%)',
  }),
  themed('solar', 'Solar Flare', 'solar.jpg', '#f59e0b', '#ea580c', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(245, 158, 11, 0.22)',
    '--accent-soft': 'rgba(234, 88, 12, 0.16)',
    '--brand-glow': 'rgba(245, 158, 11, 0.4)',
    '--panel-glass': 'rgba(20, 12, 6, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(16,8,2,0.5) 0%, rgba(16,8,2,0.18) 44%, rgba(12,6,4,0.48) 100%)',
  }),
  themed('neon', 'Neon Orchid', 'neon.jpg', '#e879f9', '#22d3ee', {
    '--text': '#f5f3ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.24)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(232, 121, 249, 0.45)',
    '--panel-glass': 'rgba(10, 8, 22, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,16,0.55) 0%, rgba(6,4,16,0.22) 42%, rgba(4,8,16,0.52) 100%)',
  }),
  themed('glacier', 'Glacier Cathedral', 'glacier.jpg', '#7dd3fc', '#67e8f9', {
    '--text': '#f0f9ff',
    '--focus-ring': 'rgba(125, 211, 252, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(125, 211, 252, 0.4)',
    '--panel-glass': 'rgba(6, 16, 24, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,10,16,0.48) 0%, rgba(4,10,16,0.18) 45%, rgba(4,12,18,0.46) 100%)',
  }),
  themed('copper', 'Copper Dusk', 'copper.jpg', '#d97706', '#2dd4bf', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(217, 119, 6, 0.22)',
    '--accent-soft': 'rgba(45, 212, 191, 0.14)',
    '--brand-glow': 'rgba(217, 119, 6, 0.38)',
    '--panel-glass': 'rgba(16, 12, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,8,4,0.52) 0%, rgba(10,8,4,0.2) 44%, rgba(8,8,8,0.5) 100%)',
  }),
  themed('nebula', 'Nebula Ink', 'nebula.jpg', '#c084fc', '#fbbf24', {
    '--text': '#faf5ff',
    '--focus-ring': 'rgba(192, 132, 252, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.12)',
    '--brand-glow': 'rgba(192, 132, 252, 0.45)',
    '--panel-glass': 'rgba(10, 6, 18, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,14,0.55) 0%, rgba(6,4,14,0.22) 42%, rgba(6,4,12,0.52) 100%)',
  }),
];

const ALIASES: Record<string, ThemeId> = {
  dark: 'midnight',
  default: 'midnight',
};

export function resolveTheme(id: string | null | undefined): Theme {
  const mapped = (id && ALIASES[id]) || id;
  return THEMES.find((t) => t.id === mapped) ?? THEMES[0];
}

export function applyTheme(id: string | null | undefined): Theme {
  const theme = resolveTheme(id);
  if (typeof document === 'undefined') return theme;
  const root = document.documentElement;
  root.dataset.theme = theme.id;
  for (const [key, value] of Object.entries(theme.vars)) {
    root.style.setProperty(key, value);
  }
  return theme;
}

export type ThemeAppearance = {
  theme: ThemeId;
  transparent: boolean;
};

export function appearanceFromWorkspace(
  ui: { theme?: string | null; transparent_panels?: boolean | null } | null | undefined,
  fallbackTheme?: string | null,
  fallbackTransparent = false
): ThemeAppearance {
  const storedTransparent = ui?.transparent_panels;
  return {
    theme: resolveTheme(ui?.theme || fallbackTheme).id,
    transparent:
      storedTransparent === undefined || storedTransparent === null
        ? fallbackTransparent
        : parseTransparentPanels(storedTransparent),
  };
}

export function parseTransparentPanels(raw: unknown): boolean {
  return raw === true || raw === 1 || raw === '1' || raw === 'true';
}

export function applyTransparentPanels(on: boolean): boolean {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.transparentPanels = on ? '1' : '0';
  }
  return on;
}
