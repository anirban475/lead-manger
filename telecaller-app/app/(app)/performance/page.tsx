import { redirect } from 'next/navigation';
import { getSession, canSeeTeam } from '@/lib/auth';
import {
  listAgents,
  getAgentByEmail,
  getScorecard,
  getDailySeries,
  getLeaderboard,
  getTopCalls,
  getBottomCalls,
  getIssueCounts,
  type DailySeriesPoint,
} from '@/lib/coachingQueries';

export const dynamic = 'force-dynamic';

type PageProps = {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function PerformancePage({ searchParams }: PageProps) {
  const session = await getSession();
  if (!session) {
    redirect('/login');
  }

  const isPrivileged = canSeeTeam(session.role);
  const myAgent = await getAgentByEmail(session.email);

  const sp = await searchParams;
  const rawAgentParam = typeof sp.agent === 'string' ? sp.agent : undefined;
  const rawFromParam = typeof sp.from === 'string' ? sp.from : undefined;
  const rawToParam = typeof sp.to === 'string' ? sp.to : undefined;

  // Security contract: Callers can ONLY see their own data, ignoring any ?agent param
  let effectiveAgentId: number | null = null;
  if (!isPrivileged) {
    effectiveAgentId = myAgent ? myAgent.id : -999;
  } else {
    if (rawAgentParam && rawAgentParam !== 'all') {
      const parsed = parseInt(rawAgentParam, 10);
      effectiveAgentId = isNaN(parsed) ? null : parsed;
    } else {
      effectiveAgentId = null; // team scope
    }
  }

  // All agents list for admin/manager picker
  const agents = isPrivileged ? await listAgents() : [];
  const selectedAgentObj =
    effectiveAgentId !== null
      ? agents.find((a) => a.id === effectiveAgentId) ||
        (myAgent?.id === effectiveAgentId ? myAgent : null)
      : null;

  // Date calculation (Default 30 days)
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);

  const defaultFromDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const defaultFromStr = defaultFromDate.toISOString().slice(0, 10);

  const fromStr = rawFromParam && /^\d{4}-\d{2}-\d{2}$/.test(rawFromParam) ? rawFromParam : defaultFromStr;
  const toStr = rawToParam && /^\d{4}-\d{2}-\d{2}$/.test(rawToParam) ? rawToParam : todayStr;

  const fromDate = new Date(`${fromStr}T00:00:00.000Z`);
  const toDate = new Date(`${toStr}T23:59:59.999Z`);

  // Previous equal-length period for delta comparison
  const periodMs = toDate.getTime() - fromDate.getTime();
  const prevToDate = new Date(fromDate.getTime() - 1);
  const prevFromDate = new Date(fromDate.getTime() - periodMs);

  // Preset dates for buttons
  const d7FromStr = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const d30FromStr = defaultFromStr;
  const monthFromStr = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-01`;

  const is7 = fromStr === d7FromStr && toStr === todayStr;
  const is30 = fromStr === d30FromStr && toStr === todayStr;
  const isMonth = fromStr === monthFromStr && toStr === todayStr;
  const isCustom = !is7 && !is30 && !isMonth;

  // Fetch performance data concurrently
  const [
    scorecard,
    prevScorecard,
    dailySeries,
    leaderboard,
    topCalls,
    bottomCalls,
    topIssues,
  ] = await Promise.all([
    getScorecard(effectiveAgentId, fromDate, toDate),
    getScorecard(effectiveAgentId, prevFromDate, prevToDate),
    getDailySeries(effectiveAgentId, fromDate, toDate),
    isPrivileged ? getLeaderboard(fromDate, toDate) : Promise.resolve([]),
    getTopCalls(effectiveAgentId, fromDate, toDate, 3),
    getBottomCalls(effectiveAgentId, fromDate, toDate, 3),
    getIssueCounts(effectiveAgentId, fromDate, toDate, 8),
  ]);

  // Deltas
  const callsDelta = scorecard.calls - prevScorecard.calls;
  const scoreDelta =
    scorecard.avg_score !== null && prevScorecard.avg_score !== null
      ? scorecard.avg_score - prevScorecard.avg_score
      : null;
  const objDelta =
    scorecard.avg_objection !== null && prevScorecard.avg_objection !== null
      ? scorecard.avg_objection - prevScorecard.avg_objection
      : null;
  const talkDelta =
    scorecard.avg_agent_talk_share !== null && prevScorecard.avg_agent_talk_share !== null
      ? scorecard.avg_agent_talk_share - prevScorecard.avg_agent_talk_share
      : null;

  const currentScopeTitle = !isPrivileged
    ? (myAgent ? myAgent.name : session.displayName)
    : effectiveAgentId === null
      ? 'Team Performance (All Agents)'
      : (selectedAgentObj?.name ?? `Agent #${effectiveAgentId}`);

  const makePresetUrl = (f: string, t: string) => {
    const params = new URLSearchParams();
    if (isPrivileged && rawAgentParam) {
      params.set('agent', rawAgentParam);
    }
    params.set('from', f);
    params.set('to', t);
    return `/performance?${params.toString()}`;
  };

  const hasNoData = scorecard.calls === 0;

  return (
    <>
      <header className="topbar">
        <div>
          <h1>Performance &amp; Coaching</h1>
          <span className="muted" style={{ fontSize: 13 }}>
            {currentScopeTitle} &bull; {fromStr} to {toStr}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="badge sky">{isPrivileged ? (effectiveAgentId === null ? 'Team Scope' : 'Agent Scope') : 'Caller Scope'}</span>
        </div>
      </header>

      <div className="content stack">
        {/* Filters bar */}
        <div className="card pad" style={{ padding: '14px 16px' }}>
          <div className="rowspread" style={{ flexWrap: 'wrap', gap: 12 }}>
            {/* Agent picker (Privileged only) */}
            {isPrivileged && (
              <form method="GET" action="/performance" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="hidden" name="from" value={fromStr} />
                <input type="hidden" name="to" value={toStr} />
                <label htmlFor="agent-select" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>
                  Agent:
                </label>
                <select
                  id="agent-select"
                  name="agent"
                  defaultValue={effectiveAgentId !== null ? String(effectiveAgentId) : 'all'}
                  className="select"
                  style={{ width: 'auto', minWidth: 160, padding: '6px 10px', fontSize: 13 }}
                >
                  <option value="all">All Agents (Team)</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
                <button type="submit" className="btn ghost" style={{ padding: '6px 12px', fontSize: 13 }}>
                  Select
                </button>
              </form>
            )}

            {/* Presets and Custom Range */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <div className="filters" style={{ margin: 0 }}>
                <a href={makePresetUrl(d7FromStr, todayStr)} className={`chip-link ${is7 ? 'active' : ''}`}>
                  7 Days
                </a>
                <a href={makePresetUrl(d30FromStr, todayStr)} className={`chip-link ${is30 ? 'active' : ''}`}>
                  30 Days
                </a>
                <a href={makePresetUrl(monthFromStr, todayStr)} className={`chip-link ${isMonth ? 'active' : ''}`}>
                  This Month
                </a>
              </div>

              {/* Custom Date Form */}
              <form method="GET" action="/performance" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                {isPrivileged && <input type="hidden" name="agent" value={rawAgentParam || 'all'} />}
                <input
                  type="date"
                  name="from"
                  defaultValue={fromStr}
                  className="input"
                  style={{ width: 'auto', padding: '5px 8px', fontSize: 12 }}
                  aria-label="From Date"
                />
                <span className="muted" style={{ fontSize: 12 }}>to</span>
                <input
                  type="date"
                  name="to"
                  defaultValue={toStr}
                  className="input"
                  style={{ width: 'auto', padding: '5px 8px', fontSize: 12 }}
                  aria-label="To Date"
                />
                <button type="submit" className={`btn ghost ${isCustom ? 'primary' : ''}`} style={{ padding: '5px 10px', fontSize: 12 }}>
                  Apply
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* Empty state notice if 0 calls */}
        {hasNoData && (
          <div className="card pad" style={{ background: 'var(--surface-sunken)', textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-strong)', marginBottom: 4 }}>
              No recorded calls in this date range
            </div>
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>
              {selectedAgentObj
                ? `${selectedAgentObj.name} has 0 scored calls between ${fromStr} and ${toStr}.`
                : `There are 0 scored calls recorded between ${fromStr} and ${toStr}.`}
            </p>
          </div>
        )}

        {/* Panel 1: Four Scorecards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          {/* Card 1: Total Calls */}
          <div className="card pad">
            <div className="section-title">Total Calls</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-strong)' }}>
              {scorecard.calls}
            </div>
            <div style={{ marginTop: 6 }}>
              <DeltaBadge delta={hasNoData && prevScorecard.calls === 0 ? null : callsDelta} />
            </div>
          </div>

          {/* Card 2: Average Score */}
          <div className="card pad">
            <div className="section-title">Average Score</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-strong)' }}>
              {scorecard.avg_score !== null ? (
                <>
                  {scorecard.avg_score.toFixed(2)}
                  <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}> / 10</span>
                </>
              ) : (
                '—'
              )}
            </div>
            <div style={{ marginTop: 6 }}>
              <DeltaBadge delta={scoreDelta} decimals={2} />
            </div>
          </div>

          {/* Card 3: Objection Handling */}
          <div className="card pad">
            <div className="section-title">Objection Handling</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-strong)' }}>
              {scorecard.avg_objection !== null ? (
                <>
                  {scorecard.avg_objection.toFixed(2)}
                  <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}> (target: 6)</span>
                </>
              ) : (
                '—'
              )}
            </div>
            <div style={{ marginTop: 6 }}>
              <DeltaBadge delta={objDelta} decimals={2} />
            </div>
          </div>

          {/* Card 4: Agent Talk Share */}
          <div className="card pad">
            <div className="rowspread" style={{ marginBottom: 4 }}>
              <div className="section-title" style={{ margin: 0 }}>Agent Talk Share</div>
              <span className="badge neutral" style={{ fontSize: 10 }}>Estimate</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-strong)' }}>
              {scorecard.avg_agent_talk_share !== null ? `${scorecard.avg_agent_talk_share.toFixed(1)}%` : '—'}
            </div>
            <div style={{ marginTop: 6 }}>
              {/* Talk share is better when lower: inverted = true */}
              <DeltaBadge delta={talkDelta} inverted={true} unit="%" decimals={1} />
            </div>
          </div>
        </div>

        {/* Panel 2: Daily Activity Series */}
        <div className="card pad">
          <div className="section-title">Daily Activity &amp; Quality</div>
          <p className="muted" style={{ marginTop: -6, marginBottom: 12, fontSize: 13 }}>
            Call volume per day (bars, left axis) against average score per day (line, right axis).
          </p>
          <DailyActivityChart data={dailySeries} />
        </div>

        {/* Panel 3: Objection Handling with target line at 6 */}
        <div className="card pad">
          <div className="section-title">Objection Handling vs Target</div>
          <p className="muted" style={{ marginTop: -6, marginBottom: 12, fontSize: 13 }}>
            Average objection handling score per day tracked against the benchmark target of 6.0.
          </p>
          <ObjectionHandlingChart data={dailySeries} />
        </div>

        {/* Panel 4: Leaderboard (Team scope only, hidden entirely for callers) */}
        {isPrivileged && (
          <div className="card pad">
            <div className="rowspread" style={{ marginBottom: 12 }}>
              <div>
                <div className="section-title" style={{ margin: 0 }}>Team Leaderboard</div>
                <p className="muted" style={{ fontSize: 13, margin: '2px 0 0 0' }}>
                  Ranked by total calls and average score for the selected period.
                </p>
              </div>
              <span className="muted" style={{ fontSize: 12 }}>{leaderboard.length} active agents</span>
            </div>

            {leaderboard.length === 0 ? (
              <div className="empty">No calls recorded across the team in this period.</div>
            ) : (
              <div className="table-responsive">
                <table className="dense-table">
                  <thead>
                    <tr>
                      <th style={{ width: 45 }}>#</th>
                      <th>Agent</th>
                      <th style={{ textAlign: 'right' }}>Calls</th>
                      <th style={{ textAlign: 'right' }}>Avg Score</th>
                      <th style={{ textAlign: 'right' }}>Objection</th>
                      <th style={{ textAlign: 'right' }}>Talk Share (est.)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((row, idx) => {
                      const isRowSelected = effectiveAgentId === row.agent_id;
                      return (
                        <tr
                          key={row.agent_id}
                          className="row-hover-highlight"
                          style={isRowSelected ? { background: 'var(--chip-sky-bg)' } : undefined}
                        >
                          <td style={{ fontWeight: 700, color: 'var(--text-muted)' }}>{idx + 1}</td>
                          <td>
                            <a
                              href={`/performance?agent=${row.agent_id}&from=${fromStr}&to=${toStr}`}
                              style={{
                                fontWeight: 600,
                                color: 'var(--color-primary-strong)',
                                textDecoration: 'underline',
                              }}
                            >
                              {row.name}
                            </a>
                            {isRowSelected && (
                              <span className="badge sky" style={{ marginLeft: 6, fontSize: 10 }}>
                                Selected
                              </span>
                            )}
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 700 }}>{row.calls}</td>
                          <td style={{ textAlign: 'right' }}>
                            <span
                              className={`badge ${
                                row.avg_score && row.avg_score >= 5
                                  ? 'good'
                                  : row.avg_score && row.avg_score >= 3.5
                                    ? 'warn'
                                    : 'bad'
                              }`}
                            >
                              {row.avg_score !== null ? row.avg_score.toFixed(2) : '—'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <span
                              className={`badge ${
                                row.avg_objection && row.avg_objection >= 6 ? 'good' : 'neutral'
                              }`}
                            >
                              {row.avg_objection !== null ? row.avg_objection.toFixed(2) : '—'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
                            {row.avg_talk_share !== null ? `${row.avg_talk_share.toFixed(1)}%` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Panel 5: Best 3 and Worst 3 calls */}
        <div className="grid-2">
          {/* Best 3 Calls */}
          <div className="card pad">
            <div className="section-title">Highest Scored Calls (Top 3)</div>
            {topCalls.length === 0 ? (
              <div className="empty">No scored calls recorded in this period.</div>
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {topCalls.map((call) => (
                  <div
                    key={call.id}
                    className="card pad"
                    style={{
                      background: 'var(--surface-sunken)',
                      boxShadow: 'none',
                      padding: 12,
                    }}
                  >
                    <div className="rowspread" style={{ alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-strong)', fontSize: 14 }}>
                          {call.customer_name || call.lead_phone || `Call #${call.id}`}
                        </div>
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                          {call.call_time ? new Date(call.call_time).toLocaleString('en-IN', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) : '—'}
                        </div>
                      </div>
                      <span className="badge good score-badge">
                        Score: <span className="n">{call.call_score !== null ? call.call_score : '—'}</span>
                      </span>
                    </div>
                    <p style={{ fontSize: 13, color: 'var(--text-body)', marginTop: 8, marginBottom: 0, lineHeight: 1.4 }}>
                      {call.summary || 'No summary available.'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Worst 3 Calls */}
          <div className="card pad">
            <div className="section-title">Lowest Scored Calls (Bottom 3)</div>
            {bottomCalls.length === 0 ? (
              <div className="empty">No scored calls recorded in this period.</div>
            ) : (
              <div className="stack" style={{ gap: 12 }}>
                {bottomCalls.map((call) => (
                  <div
                    key={call.id}
                    className="card pad"
                    style={{
                      background: 'var(--surface-sunken)',
                      boxShadow: 'none',
                      padding: 12,
                    }}
                  >
                    <div className="rowspread" style={{ alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-strong)', fontSize: 14 }}>
                          {call.customer_name || call.lead_phone || `Call #${call.id}`}
                        </div>
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                          {call.call_time ? new Date(call.call_time).toLocaleString('en-IN', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) : '—'}
                        </div>
                      </div>
                      <span className="badge bad score-badge">
                        Score: <span className="n">{call.call_score !== null ? call.call_score : '—'}</span>
                      </span>
                    </div>
                    <p style={{ fontSize: 13, color: 'var(--text-body)', marginTop: 8, marginBottom: 0, lineHeight: 1.4 }}>
                      {call.summary || 'No summary available.'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Panel 6: Top issues from getIssueCounts */}
        <div className="card pad">
          <div className="section-title">Top Recurring Issues</div>
          <p className="muted" style={{ fontSize: 13, marginTop: -6, marginBottom: 12 }}>
            Note: These are raw strings from automated coaching analysis; near-duplicate wordings are not yet merged.
          </p>

          {topIssues.length === 0 ? (
            <div className="empty">No recurring coaching issues identified in this period.</div>
          ) : (
            <div className="table-responsive">
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>Issue Description</th>
                    <th style={{ textAlign: 'right', width: 120 }}>Call Count</th>
                  </tr>
                </thead>
                <tbody>
                  {topIssues.map((issue, idx) => (
                    <tr key={idx} className="row-hover-highlight">
                      <td style={{ color: 'var(--text-strong)', fontWeight: 500 }}>{issue.text}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700 }}>{issue.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// -----------------------------------------------------------------------------
// UI Subcomponents (Inline SVG Charts & Badges)
// -----------------------------------------------------------------------------

function DeltaBadge({
  delta,
  inverted = false,
  unit = '',
  decimals = 0,
}: {
  delta: number | null;
  inverted?: boolean;
  unit?: string;
  decimals?: number;
}) {
  if (delta === null || isNaN(delta)) {
    return <span className="badge neutral" style={{ fontSize: 11 }}>— vs prev period</span>;
  }
  if (delta === 0) {
    return <span className="badge neutral" style={{ fontSize: 11 }}>0{unit} vs prev period</span>;
  }

  // When inverted is true (e.g. talk share), lower is better
  const isBetter = inverted ? delta < 0 : delta > 0;
  const tone = isBetter ? 'good' : 'bad';
  const prefix = delta > 0 ? '+' : '';
  const formatted = `${prefix}${delta.toFixed(decimals)}${unit}`;

  return (
    <span className={`badge ${tone}`} style={{ fontSize: 11 }}>
      {formatted} vs prev period
    </span>
  );
}

function DailyActivityChart({ data }: { data: DailySeriesPoint[] }) {
  if (!data || data.length === 0) {
    return <div className="empty">No daily call data available for this period.</div>;
  }

  const width = Math.max(640, data.length * 28);
  const height = 220;
  const padLeft = 45;
  const padRight = 45;
  const padTop = 25;
  const padBottom = 35;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const maxCalls = Math.max(...data.map((d) => d.calls), 5);
  const barWidth = Math.max(6, Math.min(18, (plotWidth / data.length) * 0.55));

  const scorePoints = data.map((d, i) => {
    const x = padLeft + (i + 0.5) * (plotWidth / data.length);
    const y = d.avg_score !== null ? padTop + plotHeight - (d.avg_score / 10) * plotHeight : null;
    return { x, y, score: d.avg_score, day: d.day };
  });

  const validScorePoints = scorePoints.filter(
    (p): p is { x: number; y: number; score: number; day: string } => p.y !== null,
  );

  let scorePathD = '';
  if (validScorePoints.length > 0) {
    scorePathD = validScorePoints.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, '');
  }

  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="table-responsive" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        style={{ display: 'block', maxWidth: 'none', background: 'transparent' }}
      >
        {/* Y-axis gridlines & labels */}
        {yTicks.map((t, idx) => {
          const y = padTop + plotHeight - t * plotHeight;
          const callVal = Math.round(t * maxCalls);
          const scoreVal = (t * 10).toFixed(0);
          return (
            <g key={idx}>
              <line
                x1={padLeft}
                y1={y}
                x2={padLeft + plotWidth}
                y2={y}
                stroke="var(--border-default)"
                strokeDasharray={idx === 0 ? 'none' : '3 3'}
                strokeWidth="1"
              />
              <text x={padLeft - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-muted)">
                {callVal}
              </text>
              <text x={padLeft + plotWidth + 8} y={y + 4} textAnchor="start" fontSize="10" fill="var(--text-muted)">
                {scoreVal}
              </text>
            </g>
          );
        })}

        {/* Axis titles */}
        <text x={padLeft} y={padTop - 10} fontSize="11" fontWeight="600" fill="var(--color-primary-strong)">
          Calls (bars)
        </text>
        <text x={padLeft + plotWidth} y={padTop - 10} textAnchor="end" fontSize="11" fontWeight="600" fill="var(--color-success)">
          Avg Score /10 (line)
        </text>

        {/* Bars (Calls) */}
        {data.map((d, i) => {
          const x = padLeft + (i + 0.5) * (plotWidth / data.length);
          const barHeight = (d.calls / maxCalls) * plotHeight;
          const y = padTop + plotHeight - barHeight;
          return (
            <g key={d.day}>
              <rect
                x={x - barWidth / 2}
                y={y}
                width={barWidth}
                height={Math.max(barHeight, 0)}
                fill="var(--jd-sky-400)"
                opacity="0.85"
                rx="2"
              >
                <title>{`${d.day}: ${d.calls} calls`}</title>
              </rect>
            </g>
          );
        })}

        {/* Line & Dots (Avg Score) */}
        {scorePathD && (
          <path
            d={scorePathD}
            fill="none"
            stroke="var(--color-success)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {validScorePoints.map((p) => (
          <circle
            key={p.day}
            cx={p.x}
            cy={p.y}
            r="3.5"
            fill="var(--color-success)"
            stroke="var(--surface-card)"
            strokeWidth="1.5"
          >
            <title>{`${p.day}: Score ${p.score.toFixed(2)}`}</title>
          </circle>
        ))}

        {/* X-axis date labels */}
        {data.map((d, i) => {
          const step = Math.max(1, Math.floor(data.length / 12));
          if (i % step !== 0 && i !== data.length - 1) return null;
          const x = padLeft + (i + 0.5) * (plotWidth / data.length);
          const dateLabel = d.day.slice(5);
          return (
            <text
              key={d.day}
              x={x}
              y={padTop + plotHeight + 18}
              textAnchor="middle"
              fontSize="10"
              fill="var(--text-muted)"
            >
              {dateLabel}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function ObjectionHandlingChart({ data }: { data: DailySeriesPoint[] }) {
  if (!data || data.length === 0) {
    return <div className="empty">No objection handling data available for this period.</div>;
  }

  const width = Math.max(640, data.length * 28);
  const height = 200;
  const padLeft = 45;
  const padRight = 45;
  const padTop = 25;
  const padBottom = 35;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const yTicks = [0, 2, 4, 6, 8, 10];

  const objPoints = data.map((d, i) => {
    const x = padLeft + (i + 0.5) * (plotWidth / data.length);
    const y = d.avg_objection !== null ? padTop + plotHeight - (d.avg_objection / 10) * plotHeight : null;
    return { x, y, obj: d.avg_objection, day: d.day };
  });

  const validObjPoints = objPoints.filter(
    (p): p is { x: number; y: number; obj: number; day: string } => p.y !== null,
  );

  let objPathD = '';
  if (validObjPoints.length > 0) {
    objPathD = validObjPoints.reduce((acc, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
    }, '');
  }

  const targetY = padTop + plotHeight - (6.0 / 10) * plotHeight;

  return (
    <div className="table-responsive" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        style={{ display: 'block', maxWidth: 'none', background: 'transparent' }}
      >
        {/* Grid lines */}
        {yTicks.map((val) => {
          const y = padTop + plotHeight - (val / 10) * plotHeight;
          return (
            <g key={val}>
              <line
                x1={padLeft}
                y1={y}
                x2={padLeft + plotWidth}
                y2={y}
                stroke="var(--border-default)"
                strokeDasharray={val === 0 ? 'none' : '3 3'}
                strokeWidth="1"
              />
              <text x={padLeft - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-muted)">
                {val}
              </text>
            </g>
          );
        })}

        {/* Target 6.0 Dashed Line */}
        <line
          x1={padLeft}
          y1={targetY}
          x2={padLeft + plotWidth}
          y2={targetY}
          stroke="var(--color-danger, #ef4444)"
          strokeDasharray="6 4"
          strokeWidth="1.5"
        />
        <text
          x={padLeft + plotWidth - 4}
          y={targetY - 6}
          textAnchor="end"
          fontSize="11"
          fontWeight="700"
          fill="var(--color-danger, #ef4444)"
        >
          Target: 6.0
        </text>

        {/* Objection Line & Dots */}
        {objPathD && (
          <path
            d={objPathD}
            fill="none"
            stroke="var(--jd-amber-500, #f59e0b)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {validObjPoints.map((p) => (
          <circle
            key={p.day}
            cx={p.x}
            cy={p.y}
            r="3.5"
            fill="var(--jd-amber-500, #f59e0b)"
            stroke="var(--surface-card)"
            strokeWidth="1.5"
          >
            <title>{`${p.day}: Objection Handling ${p.obj.toFixed(2)}`}</title>
          </circle>
        ))}

        {/* X-axis date labels */}
        {data.map((d, i) => {
          const step = Math.max(1, Math.floor(data.length / 12));
          if (i % step !== 0 && i !== data.length - 1) return null;
          const x = padLeft + (i + 0.5) * (plotWidth / data.length);
          const dateLabel = d.day.slice(5);
          return (
            <text
              key={d.day}
              x={x}
              y={padTop + plotHeight + 18}
              textAnchor="middle"
              fontSize="10"
              fill="var(--text-muted)"
            >
              {dateLabel}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
