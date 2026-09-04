export type CalendarCell = {
  iso: string;
  day: number;
  inMonth: boolean;
};

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

export function formatIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function parseIsoDate(raw: unknown): Date | null {
  const m = ISO.exec(String(raw ?? '').trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const dt = new Date(y, mo - 1, d);
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
  return dt;
}

export function calendarMonth(year: number, monthIndex: number): CalendarCell[] {
  const startWeekday = new Date(year, monthIndex, 1).getDay();
  const cells: CalendarCell[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(year, monthIndex, 1 - startWeekday + i);
    cells.push({
      iso: formatIsoDate(d),
      day: d.getDate(),
      inMonth: d.getMonth() === monthIndex,
    });
  }
  return cells;
}

export function monthLabel(year: number, monthIndex: number): string {
  return new Date(year, monthIndex, 1).toLocaleString(undefined, {
    month: 'long',
    year: 'numeric',
  });
}
