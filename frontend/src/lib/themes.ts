export type ThemeId =
  | 'midnight'
  | 'aurora'
  | 'ember'
  | 'abyss'
  | 'lunar'
  | 'sakura'
  | 'solar'
  | 'glacier'
  | 'verdant'
  | 'dune'
  | 'cobalt'
  | 'iris'
  | 'lacquer'
  | 'europa'
  | 'titan'
  | 'io'
  | 'triton'
  | 'phobos'
  | 'enceladus'
  | 'earthrise'
  | 'rings'
  | 'umbra'
  | 'horizon'
  | 'shibuya'
  | 'shinjuku'
  | 'dotonbori'
  | 'ginzan'
  | 'takayama'
  | 'obsidian'
  | 'biolume'
  | 'torii'
  | 'kowloon'
  | 'petra'
  | 'saguaro'
  | 'lofoten'
  | 'orchid'
  | 'polar'
  | 'karst'
  | 'opera'
  | 'reef'
  | 'geode'
  | 'fuji'
  | 'bamboo'
  | 'kinkaku'
  | 'nachi'
  | 'kasuga'
  | 'yakushima'
  | 'shirakawa'
  | 'miyajima'
  | 'koyo'
  | 'onsen'
  | 'nikko'
  | 'himeji'
  | 'aso'
  | 'kepler'
  | 'xenon'
  | 'spore'
  | 'magma'
  | 'tide'
  | 'veil'
  | 'oasis'
  | 'thorn'
  | 'nimbus'
  | 'rift'
  | 'bloom'
  | 'mirror'
  | 'forge'
  | 'mist'
  | 'halo'
  | 'vanta'
  | 'oracle'
  | 'lichen'
  | 'hanami'
  | 'yoshino'
  | 'maruyama'
  | 'meguro'
  | 'kakunodate'
  | 'hirosaki'
  | 'nara'
  | 'kamakura'
  | 'matsumoto'
  | 'kenroku'
  | 'rikugien'
  | 'chidori'
  | 'kawazu'
  | 'daigo'
  | 'osaka'
  | 'inokashira'
  | 'sekigahara'
  | 'azuchi'
  | 'kumamoto'
  | 'nagashino'
  | 'noroshi'
  | 'kagemusha'
  | 'inuyama'
  | 'kacchu'
  | 'yabusame'
  | 'ueno'
  | 'tetsugaku'
  | 'heian'
  | 'gyoen'
  | 'korakuen'
  | 'odawara'
  | 'mifuneyama'
  | 'asakusa'
  | 'koishikawa'
  | 'tsuwano';

export type Theme = {
  id: ThemeId;
  name: string;
  wallpaper?: string;
  vars: Record<string, string>;
};

export const THEME_STORAGE_KEY = 'lit:theme';
export const TRANSPARENT_PANELS_KEY = 'lit:transparent-panels';
export const TRANSPARENCY_BY_THEME_KEY = 'lit:transparency-by-theme';
/** First-time slider value when a theme has no saved transparency. */
export const DEFAULT_PANEL_TRANSPARENCY = 0.66;

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
  themed('abyss', 'Abyssal Jade', 'abyss-trench.jpg', '#22d3ee', '#34d399', {
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
  themed('glacier', 'Glacier Cathedral', 'glacier.jpg', '#7dd3fc', '#67e8f9', {
    '--text': '#f0f9ff',
    '--focus-ring': 'rgba(125, 211, 252, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(125, 211, 252, 0.4)',
    '--panel-glass': 'rgba(6, 16, 24, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,10,16,0.48) 0%, rgba(4,10,16,0.18) 45%, rgba(4,12,18,0.46) 100%)',
  }),
  themed('verdant', 'Verdant Hollow', 'verdant.jpg', '#4ade80', '#a3e635', {
    '--text': '#ecfdf3',
    '--focus-ring': 'rgba(74, 222, 128, 0.22)',
    '--accent-soft': 'rgba(163, 230, 53, 0.14)',
    '--brand-glow': 'rgba(74, 222, 128, 0.4)',
    '--panel-glass': 'rgba(6, 16, 10, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,12,8,0.52) 0%, rgba(4,12,8,0.2) 44%, rgba(4,10,8,0.5) 100%)',
  }),
  themed('dune', 'Dune Mirage', 'dune.jpg', '#fbbf24', '#fb923c', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(251, 146, 60, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(22, 14, 6, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(16,10,4,0.5) 0%, rgba(16,10,4,0.18) 44%, rgba(14,8,4,0.48) 100%)',
  }),
  themed('cobalt', 'Cobalt Harbor', 'cobalt.jpg', '#60a5fa', '#f59e0b', {
    '--text': '#eff6ff',
    '--focus-ring': 'rgba(96, 165, 250, 0.22)',
    '--accent-soft': 'rgba(245, 158, 11, 0.14)',
    '--brand-glow': 'rgba(96, 165, 250, 0.4)',
    '--panel-glass': 'rgba(6, 12, 24, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,18,0.55) 0%, rgba(4,8,18,0.22) 42%, rgba(4,8,16,0.52) 100%)',
  }),
  themed('iris', 'Iris Storm', 'iris.jpg', '#a78bfa', '#818cf8', {
    '--text': '#f5f3ff',
    '--focus-ring': 'rgba(167, 139, 250, 0.22)',
    '--accent-soft': 'rgba(129, 140, 248, 0.16)',
    '--brand-glow': 'rgba(167, 139, 250, 0.45)',
    '--panel-glass': 'rgba(10, 8, 22, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,16,0.55) 0%, rgba(6,4,16,0.22) 42%, rgba(6,6,16,0.52) 100%)',
  }),
  themed('lacquer', 'Lacquer Night', 'lacquer.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(16, 6, 8, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.55) 0%, rgba(10,4,6,0.22) 42%, rgba(8,4,6,0.52) 100%)',
  }),
  themed('europa', 'Europa Ice', 'europa.jpg', '#f59e0b', '#93c5fd', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(245, 158, 11, 0.22)',
    '--accent-soft': 'rgba(147, 197, 253, 0.16)',
    '--brand-glow': 'rgba(245, 158, 11, 0.4)',
    '--panel-glass': 'rgba(12, 10, 16, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,8,14,0.52) 0%, rgba(8,8,14,0.2) 44%, rgba(8,8,14,0.5) 100%)',
  }),
  themed('titan', 'Titan Shore', 'titan.jpg', '#fb923c', '#fcd34d', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.4)',
    '--panel-glass': 'rgba(18, 10, 6, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(12,6,2,0.52) 0%, rgba(12,6,2,0.2) 44%, rgba(10,6,4,0.5) 100%)',
  }),
  themed('io', 'Io Inferno', 'io.jpg', '#fb923c', '#facc15', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(250, 204, 21, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.42)',
    '--panel-glass': 'rgba(16, 8, 4, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,2,0.55) 0%, rgba(10,4,2,0.2) 42%, rgba(8,4,2,0.52) 100%)',
  }),
  themed('triton', 'Triton Blue', 'triton-ice.jpg', '#38bdf8', '#e0f2fe', {
    '--text': '#f0f9ff',
    '--focus-ring': 'rgba(56, 189, 248, 0.22)',
    '--accent-soft': 'rgba(224, 242, 254, 0.12)',
    '--brand-glow': 'rgba(56, 189, 248, 0.42)',
    '--panel-glass': 'rgba(6, 10, 20, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,6,14,0.55) 0%, rgba(2,6,14,0.2) 42%, rgba(4,6,14,0.52) 100%)',
  }),
  themed('phobos', 'Phobos Watch', 'phobos.jpg', '#f97316', '#fda4af', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(249, 115, 22, 0.22)',
    '--accent-soft': 'rgba(253, 164, 175, 0.14)',
    '--brand-glow': 'rgba(249, 115, 22, 0.4)',
    '--panel-glass': 'rgba(16, 8, 8, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,4,0.55) 0%, rgba(10,4,4,0.2) 42%, rgba(8,4,4,0.52) 100%)',
  }),
  themed('enceladus', 'Enceladus Ice', 'enceladus-ice.jpg', '#e2e8f0', '#fcd34d', {
    '--text': '#f8fafc',
    '--focus-ring': 'rgba(226, 232, 240, 0.2)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(226, 232, 240, 0.35)',
    '--panel-glass': 'rgba(10, 12, 18, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,6,12,0.55) 0%, rgba(4,6,12,0.2) 42%, rgba(6,6,12,0.52) 100%)',
  }),
  themed('earthrise', 'Earthrise', 'earthrise.jpg', '#38bdf8', '#e2e8f0', {
    '--text': '#f8fafc',
    '--focus-ring': 'rgba(56, 189, 248, 0.22)',
    '--accent-soft': 'rgba(226, 232, 240, 0.14)',
    '--brand-glow': 'rgba(56, 189, 248, 0.4)',
    '--panel-glass': 'rgba(8, 10, 16, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,4,10,0.55) 0%, rgba(2,4,10,0.2) 42%, rgba(4,4,10,0.52) 100%)',
  }),
  themed('rings', 'Ring Plane', 'rings.jpg', '#fbbf24', '#fde68a', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(253, 230, 138, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(12, 8, 4, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,2,0.55) 0%, rgba(8,4,2,0.2) 42%, rgba(8,6,2,0.52) 100%)',
  }),
  themed('umbra', 'Solar Umbra', 'umbra.jpg', '#fde68a', '#f43f5e', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(253, 230, 138, 0.22)',
    '--accent-soft': 'rgba(244, 63, 94, 0.14)',
    '--brand-glow': 'rgba(253, 230, 138, 0.4)',
    '--panel-glass': 'rgba(10, 6, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,2,10,0.55) 0%, rgba(6,2,10,0.2) 42%, rgba(6,4,10,0.52) 100%)',
  }),
  themed('horizon', 'Event Horizon', 'horizon.jpg', '#fb923c', '#fbbf24', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.42)',
    '--panel-glass': 'rgba(10, 6, 4, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,2,2,0.55) 0%, rgba(6,2,2,0.2) 42%, rgba(6,4,2,0.52) 100%)',
  }),
  themed('shibuya', 'Shibuya Rain', 'shibuya.jpg', '#e879f9', '#22d3ee', {
    '--text': '#fdf4ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.22)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(232, 121, 249, 0.42)',
    '--panel-glass': 'rgba(10, 6, 16, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,12,0.55) 0%, rgba(6,4,12,0.22) 42%, rgba(6,4,12,0.52) 100%)',
  }),
  themed('shinjuku', 'Shinjuku Alley', 'shinjuku-oil.jpg', '#f472b6', '#4ade80', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(74, 222, 128, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(10, 6, 12, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,10,0.58) 0%, rgba(6,4,10,0.24) 42%, rgba(6,4,10,0.55) 100%)',
  }),
  themed('dotonbori', 'Dotonbori Canal', 'dotonbori-oil.jpg', '#fb7185', '#a3e635', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(163, 230, 53, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.42)',
    '--panel-glass': 'rgba(12, 6, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,10,0.55) 0%, rgba(8,4,10,0.22) 42%, rgba(8,4,10,0.52) 100%)',
  }),
  themed('ginzan', 'Ginzan Snow', 'ginzan-oil.jpg', '#fbbf24', '#93c5fd', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(147, 197, 253, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.38)',
    '--panel-glass': 'rgba(10, 10, 16, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,14,0.5) 0%, rgba(6,8,14,0.18) 44%, rgba(6,8,14,0.48) 100%)',
  }),
  themed('takayama', 'Takayama Night', 'takayama-oil.jpg', '#f97316', '#818cf8', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(249, 115, 22, 0.22)',
    '--accent-soft': 'rgba(129, 140, 248, 0.14)',
    '--brand-glow': 'rgba(249, 115, 22, 0.4)',
    '--panel-glass': 'rgba(12, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,6,4,0.55) 0%, rgba(8,6,4,0.22) 42%, rgba(8,6,4,0.52) 100%)',
  }),
  themed('obsidian', 'Obsidian Caldera', 'obsidian.jpg', '#fb7185', '#f97316', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(249, 115, 22, 0.16)',
    '--brand-glow': 'rgba(249, 115, 22, 0.42)',
    '--panel-glass': 'rgba(16, 6, 6, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,2,2,0.58) 0%, rgba(10,2,2,0.22) 42%, rgba(8,4,4,0.55) 100%)',
  }),
  themed('biolume', 'Biolume Canopy', 'biolume.jpg', '#4ade80', '#22d3ee', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(74, 222, 128, 0.22)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(74, 222, 128, 0.42)',
    '--panel-glass': 'rgba(4, 14, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,8,8,0.55) 0%, rgba(2,8,8,0.22) 42%, rgba(2,10,8,0.52) 100%)',
  }),
  themed('torii', 'Thousand Torii', 'torii.jpg', '#f43f5e', '#fb923c', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 146, 60, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(14, 6, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,4,0.55) 0%, rgba(10,4,4,0.22) 42%, rgba(8,4,4,0.52) 100%)',
  }),
  themed('kowloon', 'Neon Harbor', 'kowloon.jpg', '#22d3ee', '#e879f9', {
    '--text': '#ecfeff',
    '--focus-ring': 'rgba(34, 211, 238, 0.22)',
    '--accent-soft': 'rgba(232, 121, 249, 0.14)',
    '--brand-glow': 'rgba(34, 211, 238, 0.42)',
    '--panel-glass': 'rgba(8, 6, 16, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,4,12,0.58) 0%, rgba(4,4,12,0.24) 42%, rgba(4,4,12,0.55) 100%)',
  }),
  themed('petra', 'Petra Gold', 'petra.jpg', '#fbbf24', '#fb923c', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(251, 146, 60, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.42)',
    '--panel-glass': 'rgba(16, 10, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,6,2,0.55) 0%, rgba(10,6,2,0.2) 42%, rgba(10,6,4,0.52) 100%)',
  }),
  themed('saguaro', 'Lightning Mesa', 'saguaro.jpg', '#a78bfa', '#f472b6', {
    '--text': '#f5f3ff',
    '--focus-ring': 'rgba(167, 139, 250, 0.22)',
    '--accent-soft': 'rgba(244, 114, 182, 0.14)',
    '--brand-glow': 'rgba(167, 139, 250, 0.42)',
    '--panel-glass': 'rgba(12, 8, 18, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,14,0.55) 0%, rgba(8,4,14,0.22) 42%, rgba(8,6,14,0.52) 100%)',
  }),
  themed('lofoten', 'Lofoten Gold', 'lofoten.jpg', '#fbbf24', '#38bdf8', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(56, 189, 248, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(8, 12, 18, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,14,0.52) 0%, rgba(4,8,14,0.2) 44%, rgba(6,8,14,0.5) 100%)',
  }),
  themed('orchid', 'Orchid Ruin', 'orchid.jpg', '#e879f9', '#f472b6', {
    '--text': '#fdf4ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.22)',
    '--accent-soft': 'rgba(244, 114, 182, 0.16)',
    '--brand-glow': 'rgba(232, 121, 249, 0.42)',
    '--panel-glass': 'rgba(12, 6, 14, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,10,0.52) 0%, rgba(8,4,10,0.2) 44%, rgba(8,4,12,0.5) 100%)',
  }),
  themed('polar', 'Polar Ember', 'polar.jpg', '#fb7185', '#38bdf8', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(56, 189, 248, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(10, 8, 14, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,10,0.52) 0%, rgba(6,4,10,0.2) 44%, rgba(6,6,12,0.5) 100%)',
  }),
  themed('karst', 'Karst Pagoda', 'karst.jpg', '#fbbf24', '#4ade80', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(74, 222, 128, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.38)',
    '--panel-glass': 'rgba(8, 12, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,6,0.5) 0%, rgba(4,8,6,0.18) 44%, rgba(4,8,8,0.48) 100%)',
  }),
  themed('opera', 'Velvet Opera', 'opera.jpg', '#fb7185', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.42)',
    '--panel-glass': 'rgba(16, 6, 10, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,2,6,0.58) 0%, rgba(10,2,6,0.22) 42%, rgba(8,4,6,0.55) 100%)',
  }),
  themed('reef', 'Coral Cathedral', 'reef.jpg', '#22d3ee', '#fb7185', {
    '--text': '#ecfeff',
    '--focus-ring': 'rgba(34, 211, 238, 0.22)',
    '--accent-soft': 'rgba(251, 113, 133, 0.14)',
    '--brand-glow': 'rgba(34, 211, 238, 0.42)',
    '--panel-glass': 'rgba(4, 14, 20, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,8,14,0.52) 0%, rgba(2,8,14,0.2) 44%, rgba(2,10,16,0.5) 100%)',
  }),
  themed('geode', 'Amethyst Geode', 'geode.jpg', '#c084fc', '#f0abfc', {
    '--text': '#faf5ff',
    '--focus-ring': 'rgba(192, 132, 252, 0.22)',
    '--accent-soft': 'rgba(240, 171, 252, 0.14)',
    '--brand-glow': 'rgba(192, 132, 252, 0.45)',
    '--panel-glass': 'rgba(12, 6, 20, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,2,16,0.55) 0%, rgba(8,2,16,0.22) 42%, rgba(8,4,16,0.52) 100%)',
  }),
  themed('fuji', 'Fuji Dawn', 'fuji.jpg', '#fb923c', '#fcd34d', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.4)',
    '--panel-glass': 'rgba(14, 10, 12, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,6,8,0.5) 0%, rgba(10,6,8,0.18) 44%, rgba(10,8,10,0.48) 100%)',
  }),
  themed('bamboo', 'Arashiyama Grove', 'bamboo.jpg', '#4ade80', '#a3e635', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(74, 222, 128, 0.22)',
    '--accent-soft': 'rgba(163, 230, 53, 0.14)',
    '--brand-glow': 'rgba(74, 222, 128, 0.4)',
    '--panel-glass': 'rgba(6, 16, 10, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,12,8,0.52) 0%, rgba(4,12,8,0.2) 44%, rgba(4,10,8,0.5) 100%)',
  }),
  themed('kinkaku', 'Golden Pavilion', 'kinkaku.jpg', '#fbbf24', '#f59e0b', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(245, 158, 11, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.45)',
    '--panel-glass': 'rgba(12, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.55) 0%, rgba(8,4,4,0.2) 42%, rgba(8,6,6,0.52) 100%)',
  }),
  themed('nachi', 'Nachi Falls', 'nachi.jpg', '#f43f5e', '#2dd4bf', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(45, 212, 191, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.4)',
    '--panel-glass': 'rgba(8, 12, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,8,0.55) 0%, rgba(4,8,8,0.22) 42%, rgba(6,8,8,0.52) 100%)',
  }),
  themed('kasuga', 'Kasuga Lanterns', 'kasuga.jpg', '#fbbf24', '#fb923c', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(251, 146, 60, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.42)',
    '--panel-glass': 'rgba(12, 8, 6, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,2,0.58) 0%, rgba(8,4,2,0.22) 42%, rgba(8,6,4,0.55) 100%)',
  }),
  themed('yakushima', 'Yakushima Moss', 'yakushima.jpg', '#34d399', '#a3e635', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(52, 211, 153, 0.22)',
    '--accent-soft': 'rgba(163, 230, 53, 0.14)',
    '--brand-glow': 'rgba(52, 211, 153, 0.4)',
    '--panel-glass': 'rgba(6, 14, 10, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,10,8,0.55) 0%, rgba(4,10,8,0.22) 42%, rgba(4,10,8,0.52) 100%)',
  }),
  themed('shirakawa', 'Shirakawa Snow', 'shirakawa.jpg', '#fbbf24', '#93c5fd', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(147, 197, 253, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.38)',
    '--panel-glass': 'rgba(10, 12, 18, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,14,0.52) 0%, rgba(6,8,14,0.2) 44%, rgba(6,8,14,0.5) 100%)',
  }),
  themed('miyajima', 'Miyajima Tide', 'miyajima.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(12, 8, 10, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,8,0.52) 0%, rgba(8,4,8,0.2) 44%, rgba(8,6,10,0.5) 100%)',
  }),
  themed('koyo', 'Maple Temple', 'koyo.jpg', '#f97316', '#f43f5e', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(249, 115, 22, 0.22)',
    '--accent-soft': 'rgba(244, 63, 94, 0.16)',
    '--brand-glow': 'rgba(249, 115, 22, 0.42)',
    '--panel-glass': 'rgba(14, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,4,0.55) 0%, rgba(10,4,4,0.2) 42%, rgba(10,6,4,0.52) 100%)',
  }),
  themed('onsen', 'Snow Onsen', 'onsen.jpg', '#fbbf24', '#67e8f9', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(10, 12, 16, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,12,0.55) 0%, rgba(6,8,12,0.22) 42%, rgba(6,8,12,0.52) 100%)',
  }),
  themed('nikko', 'Nikko Gold', 'nikko.jpg', '#fbbf24', '#4ade80', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(74, 222, 128, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.42)',
    '--panel-glass': 'rgba(8, 12, 8, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,4,0.58) 0%, rgba(4,8,4,0.22) 42%, rgba(4,8,6,0.55) 100%)',
  }),
  themed('himeji', 'White Heron', 'himeji.jpg', '#e2e8f0', '#fbbf24', {
    '--text': '#f8fafc',
    '--focus-ring': 'rgba(226, 232, 240, 0.2)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(226, 232, 240, 0.35)',
    '--panel-glass': 'rgba(12, 12, 16, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,8,12,0.5) 0%, rgba(8,8,12,0.18) 44%, rgba(8,8,12,0.48) 100%)',
  }),
  themed('aso', 'Aso Caldera', 'aso.jpg', '#fbbf24', '#34d399', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(52, 211, 153, 0.14)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(12, 10, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,6,4,0.52) 0%, rgba(8,6,4,0.2) 44%, rgba(8,6,4,0.5) 100%)',
  }),
  themed('kepler', 'Twin Suns', 'kepler.jpg', '#f59e0b', '#f43f5e', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(245, 158, 11, 0.22)',
    '--accent-soft': 'rgba(244, 63, 94, 0.14)',
    '--brand-glow': 'rgba(245, 158, 11, 0.4)',
    '--panel-glass': 'rgba(16, 8, 6, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(12,4,4,0.52) 0%, rgba(12,4,4,0.2) 44%, rgba(10,6,4,0.5) 100%)',
  }),
  themed('xenon', 'Xenon Spires', 'xenon.jpg', '#22d3ee', '#a78bfa', {
    '--text': '#ecfeff',
    '--focus-ring': 'rgba(34, 211, 238, 0.22)',
    '--accent-soft': 'rgba(167, 139, 250, 0.14)',
    '--brand-glow': 'rgba(34, 211, 238, 0.42)',
    '--panel-glass': 'rgba(8, 8, 20, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,6,16,0.52) 0%, rgba(4,6,16,0.2) 44%, rgba(6,6,16,0.5) 100%)',
  }),
  themed('spore', 'Spore Forest', 'spore.jpg', '#f472b6', '#fbbf24', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.42)',
    '--panel-glass': 'rgba(16, 6, 12, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,8,0.52) 0%, rgba(10,4,8,0.2) 44%, rgba(10,4,10,0.5) 100%)',
  }),
  themed('magma', 'Magma Glass', 'magma.jpg', '#fb923c', '#facc15', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(250, 204, 21, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.42)',
    '--panel-glass': 'rgba(16, 8, 4, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,2,0.55) 0%, rgba(10,4,2,0.2) 42%, rgba(8,4,2,0.52) 100%)',
  }),
  themed('tide', 'Twin Tide', 'tide.jpg', '#c084fc', '#e2e8f0', {
    '--text': '#faf5ff',
    '--focus-ring': 'rgba(192, 132, 252, 0.22)',
    '--accent-soft': 'rgba(226, 232, 240, 0.14)',
    '--brand-glow': 'rgba(192, 132, 252, 0.42)',
    '--panel-glass': 'rgba(10, 8, 18, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,14,0.52) 0%, rgba(6,4,14,0.2) 44%, rgba(6,6,14,0.5) 100%)',
  }),
  themed('veil', 'Sky Veil', 'veil.jpg', '#4ade80', '#fde68a', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(74, 222, 128, 0.22)',
    '--accent-soft': 'rgba(253, 230, 138, 0.14)',
    '--brand-glow': 'rgba(74, 222, 128, 0.4)',
    '--panel-glass': 'rgba(6, 12, 10, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,8,8,0.52) 0%, rgba(4,8,8,0.2) 44%, rgba(4,8,8,0.5) 100%)',
  }),
  themed('oasis', 'Sky Oasis', 'oasis.jpg', '#2dd4bf', '#fbbf24', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(45, 212, 191, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(45, 212, 191, 0.4)',
    '--panel-glass': 'rgba(6, 14, 14, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,10,10,0.5) 0%, rgba(4,10,10,0.18) 44%, rgba(4,10,10,0.48) 100%)',
  }),
  themed('thorn', 'Thorn Sea', 'thorn.jpg', '#fb923c', '#38bdf8', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(56, 189, 248, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.4)',
    '--panel-glass': 'rgba(12, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.55) 0%, rgba(8,4,4,0.2) 42%, rgba(8,6,6,0.52) 100%)',
  }),
  themed('nimbus', 'Cloud Ocean', 'nimbus.jpg', '#fda4af', '#c4b5fd', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(253, 164, 175, 0.22)',
    '--accent-soft': 'rgba(196, 181, 253, 0.14)',
    '--brand-glow': 'rgba(253, 164, 175, 0.38)',
    '--panel-glass': 'rgba(14, 10, 16, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,6,12,0.48) 0%, rgba(10,6,12,0.16) 44%, rgba(10,8,12,0.46) 100%)',
  }),
  themed('rift', 'Plasma Rift', 'rift.jpg', '#38bdf8', '#818cf8', {
    '--text': '#f0f9ff',
    '--focus-ring': 'rgba(56, 189, 248, 0.22)',
    '--accent-soft': 'rgba(129, 140, 248, 0.14)',
    '--brand-glow': 'rgba(56, 189, 248, 0.42)',
    '--panel-glass': 'rgba(6, 8, 18, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,4,12,0.55) 0%, rgba(2,4,12,0.22) 42%, rgba(4,4,12,0.52) 100%)',
  }),
  themed('bloom', 'Night Bloom', 'bloom.jpg', '#e879f9', '#22d3ee', {
    '--text': '#fdf4ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.22)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(232, 121, 249, 0.42)',
    '--panel-glass': 'rgba(10, 6, 18, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,2,14,0.55) 0%, rgba(6,2,14,0.22) 42%, rgba(6,4,14,0.52) 100%)',
  }),
  themed('mirror', 'Mirror World', 'mirror.jpg', '#93c5fd', '#fde68a', {
    '--text': '#f0f9ff',
    '--focus-ring': 'rgba(147, 197, 253, 0.22)',
    '--accent-soft': 'rgba(253, 230, 138, 0.14)',
    '--brand-glow': 'rgba(147, 197, 253, 0.4)',
    '--panel-glass': 'rgba(8, 10, 16, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,6,12,0.52) 0%, rgba(4,6,12,0.2) 44%, rgba(6,6,12,0.5) 100%)',
  }),
  themed('forge', 'Star Forge', 'forge.jpg', '#f97316', '#f43f5e', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(249, 115, 22, 0.22)',
    '--accent-soft': 'rgba(244, 63, 94, 0.16)',
    '--brand-glow': 'rgba(249, 115, 22, 0.42)',
    '--panel-glass': 'rgba(16, 6, 6, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,2,2,0.58) 0%, rgba(10,2,2,0.22) 42%, rgba(8,4,4,0.55) 100%)',
  }),
  themed('mist', 'Acid Mist', 'mist.jpg', '#a3e635', '#34d399', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(163, 230, 53, 0.22)',
    '--accent-soft': 'rgba(52, 211, 153, 0.14)',
    '--brand-glow': 'rgba(163, 230, 53, 0.4)',
    '--panel-glass': 'rgba(6, 14, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(4,10,6,0.52) 0%, rgba(4,10,6,0.2) 44%, rgba(4,10,6,0.5) 100%)',
  }),
  themed('halo', 'Ring Halo', 'halo.jpg', '#fbbf24', '#fb923c', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(251, 146, 60, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.4)',
    '--panel-glass': 'rgba(14, 10, 6, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,6,2,0.52) 0%, rgba(10,6,2,0.2) 44%, rgba(10,6,4,0.5) 100%)',
  }),
  themed('vanta', 'Vanta Shore', 'vanta.jpg', '#4ade80', '#22d3ee', {
    '--text': '#ecfdf5',
    '--focus-ring': 'rgba(74, 222, 128, 0.22)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(74, 222, 128, 0.4)',
    '--panel-glass': 'rgba(4, 12, 10, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(2,8,8,0.55) 0%, rgba(2,8,8,0.22) 42%, rgba(2,8,8,0.52) 100%)',
  }),
  themed('oracle', 'Oracle Mesa', 'oracle.jpg', '#c084fc', '#e2e8f0', {
    '--text': '#faf5ff',
    '--focus-ring': 'rgba(192, 132, 252, 0.22)',
    '--accent-soft': 'rgba(226, 232, 240, 0.14)',
    '--brand-glow': 'rgba(192, 132, 252, 0.42)',
    '--panel-glass': 'rgba(10, 8, 16, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,4,12,0.55) 0%, rgba(6,4,12,0.22) 42%, rgba(6,6,12,0.52) 100%)',
  }),
  themed('lichen', 'Lichen Range', 'lichen.jpg', '#fb923c', '#22d3ee', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(34, 211, 238, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.4)',
    '--panel-glass': 'rgba(10, 10, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,6,4,0.52) 0%, rgba(6,6,4,0.2) 44%, rgba(6,8,6,0.5) 100%)',
  }),
  themed('hanami', 'Hanami Grove', 'hanami.jpg', '#fb7185', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.42)',
    '--panel-glass': 'rgba(14, 8, 10, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,8,0.52) 0%, rgba(10,4,8,0.2) 44%, rgba(10,6,8,0.5) 100%)',
  }),
  themed('yoshino', 'Yoshino Peak', 'yoshino.jpg', '#f9a8d4', '#93c5fd', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(147, 197, 253, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(12, 8, 14, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,6,12,0.48) 0%, rgba(8,6,12,0.16) 44%, rgba(8,6,12,0.46) 100%)',
  }),
  themed('maruyama', 'Weeping Maruyama', 'maruyama.jpg', '#f472b6', '#fbbf24', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.42)',
    '--panel-glass': 'rgba(14, 6, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,2,8,0.55) 0%, rgba(10,2,8,0.22) 42%, rgba(8,4,8,0.52) 100%)',
  }),
  themed('meguro', 'Meguro Night', 'meguro.jpg', '#fb7185', '#fcd34d', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.42)',
    '--panel-glass': 'rgba(12, 6, 12, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,2,10,0.58) 0%, rgba(8,2,10,0.22) 42%, rgba(8,4,10,0.55) 100%)',
  }),
  themed('kakunodate', 'Samurai Lane', 'kakunodate.jpg', '#fb7185', '#f59e0b', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(245, 158, 11, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(14, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.52) 0%, rgba(10,4,6,0.2) 44%, rgba(10,6,6,0.5) 100%)',
  }),
  themed('hirosaki', 'Hirosaki Moat', 'hirosaki.jpg', '#f9a8d4', '#e2e8f0', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(226, 232, 240, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(12, 10, 14, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,6,10,0.5) 0%, rgba(8,6,10,0.18) 44%, rgba(8,6,10,0.48) 100%)',
  }),
  themed('nara', 'Nara Blossom', 'nara.jpg', '#f472b6', '#fbbf24', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(12, 8, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,8,0.5) 0%, rgba(8,4,8,0.18) 44%, rgba(8,6,8,0.48) 100%)',
  }),
  themed('kamakura', 'Kamakura Path', 'kamakura.jpg', '#fb7185', '#fcd34d', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(12, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,6,0.52) 0%, rgba(8,4,6,0.2) 44%, rgba(8,6,6,0.5) 100%)',
  }),
  themed('matsumoto', 'Matsumoto Keep', 'matsumoto.jpg', '#f472b6', '#cbd5e1', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(203, 213, 225, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(10, 10, 14, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,6,10,0.52) 0%, rgba(6,6,10,0.2) 44%, rgba(6,6,10,0.5) 100%)',
  }),
  themed('kenroku', 'Kenrokuen Dawn', 'kenroku.jpg', '#f9a8d4', '#fbbf24', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(12, 10, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,6,8,0.5) 0%, rgba(8,6,8,0.18) 44%, rgba(8,6,8,0.48) 100%)',
  }),
  themed('rikugien', 'Rikugien Night', 'rikugien.jpg', '#e879f9', '#fb7185', {
    '--text': '#fdf4ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.22)',
    '--accent-soft': 'rgba(251, 113, 133, 0.16)',
    '--brand-glow': 'rgba(232, 121, 249, 0.42)',
    '--panel-glass': 'rgba(12, 6, 14, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,2,10,0.58) 0%, rgba(8,2,10,0.22) 42%, rgba(8,4,10,0.55) 100%)',
  }),
  themed('chidori', 'Chidori Moat', 'chidori.jpg', '#f472b6', '#67e8f9', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(10, 8, 14, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,6,12,0.5) 0%, rgba(6,6,12,0.18) 44%, rgba(6,6,12,0.48) 100%)',
  }),
  themed('kawazu', 'Kawazu Pink', 'kawazu.jpg', '#ec4899', '#fb7185', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(236, 72, 153, 0.22)',
    '--accent-soft': 'rgba(251, 113, 133, 0.16)',
    '--brand-glow': 'rgba(236, 72, 153, 0.42)',
    '--panel-glass': 'rgba(14, 6, 12, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,2,8,0.52) 0%, rgba(10,2,8,0.2) 44%, rgba(10,4,8,0.5) 100%)',
  }),
  themed('daigo', 'Daigo Pagoda', 'daigo.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(14, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.52) 0%, rgba(10,4,6,0.2) 44%, rgba(10,6,6,0.5) 100%)',
  }),
  themed('osaka', 'Osaka Keep', 'osaka.jpg', '#f472b6', '#fbbf24', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(12, 8, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,8,0.5) 0%, rgba(8,4,8,0.18) 44%, rgba(8,6,8,0.48) 100%)',
  }),
  themed('inokashira', 'Inokashira Pond', 'inokashira.jpg', '#f9a8d4', '#67e8f9', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(10, 10, 14, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,12,0.48) 0%, rgba(6,8,12,0.16) 44%, rgba(6,8,12,0.46) 100%)',
  }),
  themed('sekigahara', 'Sekigahara Dawn', 'sekigahara.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(12, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.55) 0%, rgba(8,4,4,0.2) 44%, rgba(8,6,4,0.52) 100%)',
  }),
  themed('azuchi', 'Azuchi Keep', 'azuchi.jpg', '#fbbf24', '#f97316', {
    '--text': '#fffbeb',
    '--focus-ring': 'rgba(251, 191, 36, 0.22)',
    '--accent-soft': 'rgba(249, 115, 22, 0.16)',
    '--brand-glow': 'rgba(251, 191, 36, 0.42)',
    '--panel-glass': 'rgba(14, 8, 6, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,2,0.52) 0%, rgba(10,4,2,0.2) 44%, rgba(10,6,4,0.5) 100%)',
  }),
  themed('kumamoto', 'Kumamoto Rampart', 'kumamoto.jpg', '#e2e8f0', '#f59e0b', {
    '--text': '#f8fafc',
    '--focus-ring': 'rgba(226, 232, 240, 0.2)',
    '--accent-soft': 'rgba(245, 158, 11, 0.14)',
    '--brand-glow': 'rgba(226, 232, 240, 0.35)',
    '--panel-glass': 'rgba(10, 10, 12, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,6,8,0.55) 0%, rgba(6,6,8,0.22) 42%, rgba(6,6,8,0.52) 100%)',
  }),
  themed('nagashino', 'Nagashino Palisade', 'nagashino.jpg', '#fb923c', '#94a3b8', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(251, 146, 60, 0.22)',
    '--accent-soft': 'rgba(148, 163, 184, 0.14)',
    '--brand-glow': 'rgba(251, 146, 60, 0.4)',
    '--panel-glass': 'rgba(12, 8, 8, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.55) 0%, rgba(8,4,4,0.22) 42%, rgba(8,6,6,0.52) 100%)',
  }),
  themed('noroshi', 'Signal Fires', 'noroshi.jpg', '#f97316', '#fbbf24', {
    '--text': '#fff7ed',
    '--focus-ring': 'rgba(249, 115, 22, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.16)',
    '--brand-glow': 'rgba(249, 115, 22, 0.42)',
    '--panel-glass': 'rgba(10, 6, 8, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,2,4,0.58) 0%, rgba(6,2,4,0.22) 42%, rgba(6,4,6,0.55) 100%)',
  }),
  themed('kagemusha', 'Banner Tide', 'kagemusha.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(12, 8, 6, 0.62)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.55) 0%, rgba(8,4,4,0.2) 44%, rgba(8,6,4,0.52) 100%)',
  }),
  themed('inuyama', 'Inuyama Keep', 'inuyama.jpg', '#f8fafc', '#f59e0b', {
    '--text': '#f8fafc',
    '--focus-ring': 'rgba(248, 250, 252, 0.2)',
    '--accent-soft': 'rgba(245, 158, 11, 0.14)',
    '--brand-glow': 'rgba(245, 158, 11, 0.38)',
    '--panel-glass': 'rgba(10, 12, 12, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,8,0.5) 0%, rgba(6,8,8,0.18) 44%, rgba(6,8,8,0.48) 100%)',
  }),
  themed('kacchu', 'Armor Gate', 'kacchu.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(12, 6, 6, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,2,2,0.58) 0%, rgba(8,2,2,0.22) 42%, rgba(8,4,4,0.55) 100%)',
  }),
  themed('yabusame', 'Yabusame Ground', 'yabusame.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.4)',
    '--panel-glass': 'rgba(12, 8, 6, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,4,0.52) 0%, rgba(8,4,4,0.2) 44%, rgba(8,6,4,0.5) 100%)',
  }),
  themed('ueno', 'Ueno Canopy', 'ueno.jpg', '#fb7185', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(12, 8, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,8,0.5) 0%, rgba(8,4,8,0.18) 44%, rgba(8,6,8,0.48) 100%)',
  }),
  themed('tetsugaku', 'Philosopher Path', 'tetsugaku.jpg', '#f9a8d4', '#67e8f9', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(103, 232, 249, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(10, 10, 14, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,12,0.48) 0%, rgba(6,8,12,0.16) 44%, rgba(6,8,12,0.46) 100%)',
  }),
  themed('heian', 'Heian Shrine', 'heian.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(14, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.52) 0%, rgba(10,4,6,0.2) 44%, rgba(10,6,6,0.5) 100%)',
  }),
  themed('gyoen', 'Gyoen Lawn', 'gyoen.jpg', '#f9a8d4', '#a3e635', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(163, 230, 53, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(10, 12, 10, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,6,0.48) 0%, rgba(6,8,6,0.16) 44%, rgba(6,8,6,0.46) 100%)',
  }),
  themed('korakuen', 'Korakuen Pond', 'korakuen.jpg', '#f472b6', '#38bdf8', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(244, 114, 182, 0.22)',
    '--accent-soft': 'rgba(56, 189, 248, 0.14)',
    '--brand-glow': 'rgba(244, 114, 182, 0.4)',
    '--panel-glass': 'rgba(10, 10, 14, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,12,0.5) 0%, rgba(6,8,12,0.18) 44%, rgba(6,8,12,0.48) 100%)',
  }),
  themed('odawara', 'Odawara Keep', 'odawara.jpg', '#fb7185', '#fcd34d', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(252, 211, 77, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(12, 8, 10, 0.58)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,4,8,0.5) 0%, rgba(8,4,8,0.18) 44%, rgba(8,6,8,0.48) 100%)',
  }),
  themed('mifuneyama', 'Mifuneyama Night', 'mifuneyama.jpg', '#e879f9', '#fb7185', {
    '--text': '#fdf4ff',
    '--focus-ring': 'rgba(232, 121, 249, 0.22)',
    '--accent-soft': 'rgba(251, 113, 133, 0.16)',
    '--brand-glow': 'rgba(232, 121, 249, 0.42)',
    '--panel-glass': 'rgba(12, 6, 14, 0.64)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(8,2,10,0.58) 0%, rgba(8,2,10,0.22) 42%, rgba(8,4,10,0.55) 100%)',
  }),
  themed('asakusa', 'Asakusa Bloom', 'asakusa.jpg', '#f43f5e', '#fbbf24', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(244, 63, 94, 0.22)',
    '--accent-soft': 'rgba(251, 191, 36, 0.14)',
    '--brand-glow': 'rgba(244, 63, 94, 0.42)',
    '--panel-glass': 'rgba(14, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.52) 0%, rgba(10,4,6,0.2) 44%, rgba(10,6,6,0.5) 100%)',
  }),
  themed('koishikawa', 'Koishikawa Garden', 'koishikawa.jpg', '#f9a8d4', '#4ade80', {
    '--text': '#fff1f7',
    '--focus-ring': 'rgba(249, 168, 212, 0.22)',
    '--accent-soft': 'rgba(74, 222, 128, 0.14)',
    '--brand-glow': 'rgba(249, 168, 212, 0.4)',
    '--panel-glass': 'rgba(10, 12, 10, 0.56)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(6,8,6,0.48) 0%, rgba(6,8,6,0.16) 44%, rgba(6,8,6,0.46) 100%)',
  }),
  themed('tsuwano', 'Tsuwano Lane', 'tsuwano.jpg', '#fb7185', '#f59e0b', {
    '--text': '#fff1f2',
    '--focus-ring': 'rgba(251, 113, 133, 0.22)',
    '--accent-soft': 'rgba(245, 158, 11, 0.14)',
    '--brand-glow': 'rgba(251, 113, 133, 0.4)',
    '--panel-glass': 'rgba(14, 8, 8, 0.6)',
    '--wallpaper-veil':
      'linear-gradient(180deg, rgba(10,4,6,0.52) 0%, rgba(10,4,6,0.2) 44%, rgba(10,6,6,0.5) 100%)',
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

export function clampTransparency(raw: unknown): number {
  const n = typeof raw === 'number' ? raw : typeof raw === 'string' ? Number(raw) : NaN;
  if (!Number.isFinite(n)) return DEFAULT_PANEL_TRANSPARENCY;
  return Math.min(1, Math.max(0, n));
}

export function parseTransparencyMap(raw: unknown): Record<string, number> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!(key in ALIASES) && !THEMES.some((t) => t.id === key)) continue;
    out[resolveTheme(key).id] = clampTransparency(value);
  }
  return out;
}

export function transparencyForTheme(
  id: string | null | undefined,
  map: Record<string, number> | null | undefined
): number {
  const themeId = resolveTheme(id).id;
  const stored = map?.[themeId];
  return stored === undefined ? DEFAULT_PANEL_TRANSPARENCY : clampTransparency(stored);
}

export function applyPanelTransparency(amount: unknown): number {
  const n = clampTransparency(amount);
  if (typeof document !== 'undefined') {
    document.documentElement.style.setProperty('--panel-transparency', String(n));
  }
  return n;
}
