import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getLead, getLeadCalls, getLeadComments } from '@/lib/queries';
import { ScoreBadge, TierBadge, DispositionPill, StatusBadge } from '@/components/Badges';
import CallButtons from '@/components/CallButtons';
import LogCallForm from '@/components/LogCallForm';
import CommentForm from '@/components/CommentForm';
import { fmtDate, fmtDateTime } from '@/lib/format';

export const dynamic = 'force-dynamic';

function contactOrEnrich(v: string | null): string {
  return v && v.trim() !== '' && v.trim() !== '-' ? v : 'needs enrichment';
}

export default async function LeadPage({ params }: { params: Promise<{ company_key: string }> }) {
  const { company_key } = await params;
  const key = decodeURIComponent(company_key);
  const lead = await getLead(key);
  if (!lead) notFound();
  const calls = await getLeadCalls(key);
  const comments = await getLeadComments(key);

  return (
    <>
      <header className="topbar">
        <div>
          <Link href="/queue" className="backlink">
            ← Queue
          </Link>
          <h1 style={{ marginTop: 4 }}>{lead.company_name || lead.company_key}</h1>
        </div>
        <ScoreBadge score={lead.score} tier={lead.tier} />
      </header>

      <div className="content">
        <div className="grid-2">
          <div className="stack">
            <div className="card pad">
              <div className="tags" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
                <TierBadge tier={lead.tier} />
                <StatusBadge status={lead.status} />
                {lead.last_disposition ? <DispositionPill disposition={lead.last_disposition} /> : null}
                {lead.role_group ? <span className="badge neutral">{lead.role_group}</span> : null}
              </div>

              {lead.apply_count ? (
                <div style={{ marginBottom: 12 }}>
                  <span className="badge hot" style={{ fontSize: '14px', padding: '4px 10px' }}>
                    🚨 {lead.apply_count} applicants (High Demand)
                  </span>
                </div>
              ) : null}

              {lead.contact_name ? (
                <div style={{ marginBottom: 16, fontSize: '16px', fontWeight: 600 }}>
                  👤 Ask for: <span style={{ color: 'var(--color-primary-strong)' }}>{lead.contact_name}</span>
                  {lead.contact_title ? <span className="muted" style={{ fontWeight: 500, fontSize: '14px' }}> · {lead.contact_title}</span> : ''}
                </div>
              ) : null}

              <CallButtons phone={lead.contact_phone} size="lg" />

              <dl className="kv" style={{ marginTop: 16 }}>
                <dt>City</dt>
                <dd>{lead.city || '—'}</dd>
                <dt>Industry</dt>
                <dd>{lead.industry_label || lead.industry || '—'}</dd>
                <dt>Size</dt>
                <dd>{lead.size || '—'}</dd>
                <dt>Phone</dt>
                <dd>{contactOrEnrich(lead.contact_phone)}</dd>
                <dt>Email</dt>
                <dd>{contactOrEnrich(lead.contact_email)}</dd>
                <dt>Contact via</dt>
                <dd>{lead.contact_source || '—'}</dd>
                <dt>Website</dt>
                <dd>
                  {lead.company_website ? (
                    <a href={lead.company_website} target="_blank" rel="noopener noreferrer" className="backlink">
                      {lead.company_website}
                    </a>
                  ) : (
                    '—'
                  )}
                </dd>
                <dt>Roles</dt>
                <dd>{lead.role_titles?.length ? lead.role_titles.join(', ') : (lead.roles_count ?? '—')}</dd>
                <dt>Posted</dt>
                <dd>{fmtDate(lead.posted_date)}</dd>
                <dt>Found via</dt>
                <dd>{lead.source_query || '—'}</dd>
                <dt>Next action</dt>
                <dd>
                  {lead.next_action || '—'}
                  {lead.next_action_date ? ` (${fmtDate(lead.next_action_date)})` : ''}
                </dd>
                <dt>Calls</dt>
                <dd>
                  {lead.call_count}
                  {lead.last_called_at ? ` · last ${fmtDateTime(lead.last_called_at)}` : ''}
                </dd>
              </dl>

              {lead.job_urls?.length ? (
                <div style={{ marginTop: 12 }}>
                  {lead.job_urls.map((u, i) => (
                    <a
                      key={i}
                      href={u}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="backlink"
                      style={{ display: 'block', marginTop: 2 }}
                    >
                      Job posting {i + 1} ↗
                    </a>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="card pad">
              <div className="section-title">Comments</div>
              <CommentForm companyKey={lead.company_key} />
            </div>

            <div className="card pad">
              <div className="section-title">Activity History</div>
              <div className="stack">
                {(() => {
                  type TimelineItem =
                    | { type: 'call'; id: number; timestamp: string; data: typeof calls[number] }
                    | { type: 'comment'; id: number; timestamp: string; data: typeof comments[number] };

                  const timeline: TimelineItem[] = [
                    ...calls.map((c) => ({ type: 'call' as const, id: c.id, timestamp: c.called_at, data: c })),
                    ...comments.map((cm) => ({ type: 'comment' as const, id: cm.id, timestamp: cm.created_at, data: cm })),
                  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

                  return timeline.map((item) => {
                    if (item.type === 'call') {
                      const c = item.data;
                      return (
                        <div key={`call-${c.id}`} className="call-log-item">
                          <div className="rowspread" style={{ alignItems: 'center' }}>
                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>📞</span>
                              <DispositionPill disposition={c.disposition} />
                            </div>
                            <span className="faint">{fmtDateTime(c.called_at)}</span>
                          </div>
                          {c.notes ? <div style={{ marginTop: 4 }}>{c.notes}</div> : null}
                          <div className="faint" style={{ marginTop: 2, fontSize: 12 }}>
                            Logged by {c.caller}
                            {c.follow_up_date ? ` · follow-up ${fmtDate(c.follow_up_date)}` : ''}
                          </div>
                        </div>
                      );
                    } else {
                      const cm = item.data;
                      return (
                        <div key={`comment-${cm.id}`} className="call-log-item" style={{ borderLeft: '3px solid var(--color-primary-strong)', paddingLeft: 8 }}>
                          <div className="rowspread" style={{ alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: 13 }}>
                              💬 Comment by {cm.author}
                            </span>
                            <span className="faint">{fmtDateTime(cm.created_at)}</span>
                          </div>
                          <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{cm.body}</div>
                        </div>
                      );
                    }
                  });
                })()}

                {calls.length === 0 && comments.length === 0 ? (
                  <div className="faint" style={{ fontSize: 13, textAlign: 'center', padding: 8 }}>
                    No activity logged yet.
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="card pad">
            <div className="section-title">Log a call</div>
            <LogCallForm companyKey={lead.company_key} />
          </div>
        </div>
      </div>
    </>
  );
}
