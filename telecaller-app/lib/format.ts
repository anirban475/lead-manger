const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** 'YYYY-MM-DD...' -> '9 Jul'. Dates are selected as text from Postgres to avoid TZ drift. */
export function fmtDate(v: string | null | undefined): string {
  if (!v) return '—';
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return v;
  return `${parseInt(m[3], 10)} ${MONTHS[parseInt(m[2], 10) - 1]}`;
}

/** 'YYYY-MM-DD HH:MM...' -> '9 Jul, 14:05'. */
export function fmtDateTime(v: string | null | undefined): string {
  if (!v) return '—';
  const d = v.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!d) return fmtDate(v);
  return `${parseInt(d[3], 10)} ${MONTHS[parseInt(d[2], 10) - 1]}, ${d[4]}:${d[5]}`;
}

export function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
