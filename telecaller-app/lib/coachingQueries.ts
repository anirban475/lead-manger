import { coachingQuery } from './coachingDb';

export type AgentRow = {
  id: number;
  name: string;
  folder_name: string;
  app_user_email: string | null;
};

export type ToneCounts = {
  positive: number;
  neutral: number;
  aggressive: number;
  [key: string]: number;
};

export type Scorecard = {
  calls: number;
  avg_score: number | null;
  avg_objection: number | null;
  avg_agent_talk_share: number | null;
  tone_positive?: number;
  tone_neutral?: number;
  tone_aggressive?: number;
  tone_counts: ToneCounts;
};

export type DailySeriesPoint = {
  day: string;
  calls: number;
  avg_score: number | null;
  avg_objection: number | null;
};

export type LeaderboardRow = {
  agent_id: number;
  name: string;
  calls: number;
  avg_score: number | null;
  avg_objection: number | null;
  avg_talk_share: number | null;
};

export type CallSummaryRow = {
  id: number;
  call_time: string;
  customer_name: string | null;
  lead_phone: string | null;
  call_score: number | null;
  summary: string | null;
};

export type IssueCountRow = {
  text: string;
  count: number;
};

const JUNK_TALK_RATIO_FILTER = `(analysis->>'talk_ratio' IS NULL OR analysis->>'talk_ratio' NOT IN ('0/0', '100/0', '0/100'))`;
const JUNK_TALK_RATIO_FILTER_C = `(c.analysis->>'talk_ratio' IS NULL OR c.analysis->>'talk_ratio' NOT IN ('0/0', '100/0', '0/100'))`;

export async function listAgents(): Promise<AgentRow[]> {
  const sql = `
    SELECT id, name, folder_name, app_user_email
    FROM agents
    ORDER BY id ASC
  `;
  return coachingQuery<AgentRow>(sql);
}

export async function getAgentByEmail(email: string): Promise<AgentRow | null> {
  const sql = `
    SELECT id, name, folder_name, app_user_email
    FROM agents
    WHERE app_user_email = $1
    LIMIT 1
  `;
  const rows = await coachingQuery<AgentRow>(sql, [email]);
  return rows[0] ?? null;
}

export async function getScorecard(
  agentId: number | null,
  from?: string | Date | null,
  to?: string | Date | null,
): Promise<Scorecard> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER];

  if (agentId !== null && agentId !== undefined) {
    params.push(agentId);
    where.push(`agent_id = $${params.length}`);
  }
  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`call_time <= $${params.length}`);
  }

  const sql = `
    SELECT
      COUNT(*)::int AS calls,
      ROUND(AVG(call_score), 2)::float AS avg_score,
      ROUND(AVG((analysis->>'objection_handling')::numeric), 2)::float AS avg_objection,
      ROUND(AVG(CASE WHEN analysis->>'talk_ratio' ~ '^[0-9]+/[0-9]+$' THEN split_part(analysis->>'talk_ratio', '/', 1)::numeric ELSE NULL END), 2)::float AS avg_agent_talk_share,
      COUNT(*) FILTER (WHERE analysis->>'tone' = 'positive')::int AS tone_positive,
      COUNT(*) FILTER (WHERE analysis->>'tone' = 'neutral')::int AS tone_neutral,
      COUNT(*) FILTER (WHERE analysis->>'tone' = 'aggressive')::int AS tone_aggressive,
      jsonb_build_object(
        'positive', COUNT(*) FILTER (WHERE analysis->>'tone' = 'positive')::int,
        'neutral', COUNT(*) FILTER (WHERE analysis->>'tone' = 'neutral')::int,
        'aggressive', COUNT(*) FILTER (WHERE analysis->>'tone' = 'aggressive')::int
      ) AS tone_counts
    FROM calls
    WHERE ${where.join(' AND ')}
  `;

  const rows = await coachingQuery<Scorecard>(sql, params);
  return rows[0] ?? {
    calls: 0,
    avg_score: null,
    avg_objection: null,
    avg_agent_talk_share: null,
    tone_positive: 0,
    tone_neutral: 0,
    tone_aggressive: 0,
    tone_counts: { positive: 0, neutral: 0, aggressive: 0 },
  };
}

export async function getDailySeries(
  agentId: number | null,
  from?: string | Date | null,
  to?: string | Date | null,
): Promise<DailySeriesPoint[]> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER];

  if (agentId !== null && agentId !== undefined) {
    params.push(agentId);
    where.push(`agent_id = $${params.length}`);
  }
  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`call_time <= $${params.length}`);
  }

  const sql = `
    SELECT
      call_time::date::text AS day,
      COUNT(*)::int AS calls,
      ROUND(AVG(call_score), 2)::float AS avg_score,
      ROUND(AVG((analysis->>'objection_handling')::numeric), 2)::float AS avg_objection
    FROM calls
    WHERE ${where.join(' AND ')}
    GROUP BY call_time::date
    ORDER BY day ASC
  `;

  return coachingQuery<DailySeriesPoint>(sql, params);
}

export async function getLeaderboard(
  from?: string | Date | null,
  to?: string | Date | null,
): Promise<LeaderboardRow[]> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER_C];

  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`c.call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`c.call_time <= $${params.length}`);
  }

  const sql = `
    SELECT
      a.id AS agent_id,
      a.name,
      COUNT(c.id)::int AS calls,
      ROUND(AVG(c.call_score), 2)::float AS avg_score,
      ROUND(AVG((c.analysis->>'objection_handling')::numeric), 2)::float AS avg_objection,
      ROUND(AVG(CASE WHEN c.analysis->>'talk_ratio' ~ '^[0-9]+/[0-9]+$' THEN split_part(c.analysis->>'talk_ratio', '/', 1)::numeric ELSE NULL END), 2)::float AS avg_talk_share
    FROM agents a
    JOIN calls c ON a.id = c.agent_id
    WHERE ${where.join(' AND ')}
    GROUP BY a.id, a.name
    ORDER BY calls DESC, avg_score DESC NULLS LAST
  `;

  return coachingQuery<LeaderboardRow>(sql, params);
}

export async function getTopCalls(
  agentId: number | null,
  from?: string | Date | null,
  to?: string | Date | null,
  limit: number = 10,
): Promise<CallSummaryRow[]> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER];

  if (agentId !== null && agentId !== undefined) {
    params.push(agentId);
    where.push(`agent_id = $${params.length}`);
  }
  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`call_time <= $${params.length}`);
  }

  params.push(limit);
  const limitParam = `$${params.length}`;

  const sql = `
    SELECT
      id,
      call_time::text AS call_time,
      customer_name,
      lead_phone,
      call_score::float AS call_score,
      summary
    FROM calls
    WHERE ${where.join(' AND ')}
    ORDER BY call_score DESC NULLS LAST, call_time DESC
    LIMIT ${limitParam}
  `;

  return coachingQuery<CallSummaryRow>(sql, params);
}

export async function getBottomCalls(
  agentId: number | null,
  from?: string | Date | null,
  to?: string | Date | null,
  limit: number = 10,
): Promise<CallSummaryRow[]> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER];

  if (agentId !== null && agentId !== undefined) {
    params.push(agentId);
    where.push(`agent_id = $${params.length}`);
  }
  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`call_time <= $${params.length}`);
  }

  params.push(limit);
  const limitParam = `$${params.length}`;

  const sql = `
    SELECT
      id,
      call_time::text AS call_time,
      customer_name,
      lead_phone,
      call_score::float AS call_score,
      summary
    FROM calls
    WHERE ${where.join(' AND ')}
    ORDER BY call_score ASC NULLS LAST, call_time DESC
    LIMIT ${limitParam}
  `;

  return coachingQuery<CallSummaryRow>(sql, params);
}

export async function getIssueCounts(
  agentId: number | null,
  from?: string | Date | null,
  to?: string | Date | null,
  limit: number = 10,
): Promise<IssueCountRow[]> {
  const params: unknown[] = [];
  const where: string[] = [JUNK_TALK_RATIO_FILTER_C];

  if (agentId !== null && agentId !== undefined) {
    params.push(agentId);
    where.push(`c.agent_id = $${params.length}`);
  }
  if (from) {
    params.push(from instanceof Date ? from.toISOString() : from);
    where.push(`c.call_time >= $${params.length}`);
  }
  if (to) {
    params.push(to instanceof Date ? to.toISOString() : to);
    where.push(`c.call_time <= $${params.length}`);
  }

  params.push(limit);
  const limitParam = `$${params.length}`;

  const sql = `
    SELECT
      issue AS text,
      COUNT(*)::int AS count
    FROM calls c
    CROSS JOIN LATERAL jsonb_array_elements_text(
      CASE WHEN jsonb_typeof(c.analysis->'key_issues') = 'array' THEN c.analysis->'key_issues' ELSE '[]'::jsonb END
    ) AS issue
    WHERE ${where.join(' AND ')}
    GROUP BY issue
    ORDER BY count DESC, text ASC
    LIMIT ${limitParam}
  `;

  return coachingQuery<IssueCountRow>(sql, params);
}
