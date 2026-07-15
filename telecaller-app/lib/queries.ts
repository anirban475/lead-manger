import { query } from './db';

export type Lead = {
  company_key: string;
  company_name: string | null;
  industry: string | null;
  size: string | null;
  city: string | null;
  roles_count: number | null;
  role_titles: string[] | null;
  posted_date: string | null;
  job_urls: string[] | null;
  contact_phone: string | null;
  contact_email: string | null;
  contact_source: string | null;
  company_website: string | null;
  score: number | null;
  tier: string | null;
  status: string;
  next_action: string | null;
  next_action_date: string | null;
  source_query: string | null;
  apply_count: number | null;
  role_group: string | null;
  industry_label: string | null;
  contact_name: string | null;
  contact_title: string | null;
  last_disposition: string | null;
  last_called_at: string | null;
  call_count: number;
  origin: string;
};

// Dates cast to text so node-postgres returns 'YYYY-MM-DD' strings (no TZ drift).
const LEAD_COLS = `
  company_key, company_name, industry, size, city, roles_count, role_titles,
  posted_date::text AS posted_date, job_urls, contact_phone, contact_email,
  contact_source, company_website, score, tier, status, next_action,
  next_action_date::text AS next_action_date, source_query,
  apply_count, role_group, industry_label, contact_name, contact_title,
  last_disposition, last_called_at::text AS last_called_at, call_count, origin`;

const CLOSED = `('won','lost','opted_out')`;

// A telecaller only sees leads she can actually dial (mirrors normalizePhone's >= 8-digit threshold).
const HAS_PHONE = `contact_phone IS NOT NULL AND length(regexp_replace(contact_phone, '[^0-9]', '', 'g')) >= 8`;

export async function getQueue(opts: { tier?: string } = {}): Promise<Lead[]> {
  const where: string[] = [`status NOT IN ${CLOSED}`, HAS_PHONE];
  const params: unknown[] = [];
  if (opts.tier) {
    params.push(opts.tier);
    where.push(`tier = $${params.length}`);
  }
  const sql = `
    SELECT ${LEAD_COLS} FROM leads
    WHERE ${where.join(' AND ')}
    ORDER BY score DESC NULLS LAST,
             (next_action_date IS NOT NULL AND next_action_date <= current_date) DESC,
             apply_count DESC NULLS LAST,
             posted_date DESC NULLS LAST
    LIMIT 200`;
  return query<Lead>(sql, params);
}

export async function getFollowups(): Promise<Lead[]> {
  const sql = `
    SELECT ${LEAD_COLS} FROM leads
    WHERE next_action_date IS NOT NULL
      AND next_action_date <= current_date
      AND status NOT IN ${CLOSED}
      AND ${HAS_PHONE}
    ORDER BY next_action_date ASC, score DESC NULLS LAST
    LIMIT 200`;
  return query<Lead>(sql);
}

export async function getLead(companyKey: string): Promise<Lead | null> {
  const rows = await query<Lead>(`SELECT ${LEAD_COLS} FROM leads WHERE company_key = $1`, [companyKey]);
  return rows[0] ?? null;
}

export type CallLog = {
  id: number;
  called_at: string;
  caller: string;
  channel: string;
  disposition: string;
  reason: string | null;
  notes: string | null;
  follow_up_date: string | null;
};

export async function getLeadCalls(companyKey: string): Promise<CallLog[]> {
  return query<CallLog>(
    `SELECT id, called_at::text AS called_at, caller, channel, disposition, reason, notes,
            follow_up_date::text AS follow_up_date
     FROM telecall_logs WHERE company_key = $1 ORDER BY called_at DESC`,
    [companyKey],
  );
}

export type LeadComment = {
  id: number;
  author: string;
  body: string;
  created_at: string;
};

export async function getLeadComments(companyKey: string): Promise<LeadComment[]> {
  return query<LeadComment>(
    `SELECT id, author, body, created_at::text AS created_at
     FROM lead_comments WHERE company_key = $1 ORDER BY created_at DESC`,
    [companyKey],
  );
}

export type DispositionCount = { disposition: string; n: string };

export async function getDispositionCounts(): Promise<DispositionCount[]> {
  return query<DispositionCount>(
    `SELECT disposition, count(*)::text AS n FROM telecall_logs GROUP BY disposition ORDER BY count(*) DESC`,
  );
}

export type QueryConversion = {
  source_query: string;
  companies: string;
  hot_companies: string;
  avg_score: string | null;
  contacted_companies: string;
  interested_calls: string;
  converted_calls: string;
  meeting_calls: string;
  registered_calls: string;
  positive_companies: string;
};

export async function getQueryConversion(): Promise<QueryConversion[]> {
  return query<QueryConversion>(
    `SELECT source_query, companies::text, hot_companies::text, avg_score::text,
            contacted_companies::text, interested_calls::text, converted_calls::text,
            meeting_calls::text, registered_calls::text, positive_companies::text
     FROM query_conversion
     ORDER BY positive_companies DESC, hot_companies DESC, companies DESC
     LIMIT 100`,
  );
}

export type TimelineItem =
  | { type: 'call'; id: number; timestamp: string; data: CallLog }
  | { type: 'comment'; id: number; timestamp: string; data: LeadComment };

export async function getLeadActivity(companyKey: string): Promise<TimelineItem[]> {
  const [calls, comments] = await Promise.all([
    getLeadCalls(companyKey),
    getLeadComments(companyKey),
  ]);

  return [
    ...calls.map((c) => ({ type: 'call' as const, id: c.id, timestamp: c.called_at, data: c })),
    ...comments.map((cm) => ({ type: 'comment' as const, id: cm.id, timestamp: cm.created_at, data: cm })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

