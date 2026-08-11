export function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

export function mixHex(a: string, b: string, t: number): string {
  const A = hexToRgb(a);
  const B = hexToRgb(b);
  if (!A || !B) return b;
  const u = clamp01(t);
  const r = Math.round(A.r + (B.r - A.r) * u);
  const g = Math.round(A.g + (B.g - A.g) * u);
  const bl = Math.round(A.b + (B.b - A.b) * u);
  return `#${((1 << 24) + (r << 16) + (g << 8) + bl).toString(16).slice(1)}`;
}

export function panelColors(
  fields: Record<string, unknown>,
  coding: {
    color_by_field: string;
    intensity_by_field: string;
    intensity_min: number;
    intensity_max: number;
    palette: Record<string, string>;
  } | undefined,
  neutral = '#161a22'
): { bg: string; border: string } {
  if (!coding) return { bg: neutral, border: '#2a3140' };
  const key = String(fields[coding.color_by_field] ?? '');
  const base = coding.palette[key] || '#3a4458';
  const raw = Number(fields[coding.intensity_by_field] ?? coding.intensity_min);
  const min = coding.intensity_min;
  const max = coding.intensity_max;
  const t = max === min ? 0.5 : clamp01((raw - min) / (max - min));
  // Higher priority (lower number) → stronger intensity when priority is 1..10 with 1 highest
  // Design: intensity from field as-is; for priority 1=highest we invert if field is priority
  let intensity = t;
  if (coding.intensity_by_field === 'priority') {
    intensity = 1 - t;
  }
  const bg = mixHex(neutral, base, 0.25 + 0.55 * intensity);
  return { bg, border: base };
}
