import Link from 'next/link';
import { ScoreBadge, DispositionPill } from './Badges';
import { fmtDate, truncate } from '@/lib/format';
import type { Lead } from '@/lib/queries';

export default function LeadCard({ lead }: { lead: Lead }) {
  return (
    <Link href={`/leads/${encodeURIComponent(lead.company_key)}`} className="card lead-card">
      <div className="row1">
        <div>
          <div className="name">{lead.company_name || lead.company_key}</div>
          <div className="meta">{[lead.city, lead.industry_label || lead.industry].filter(Boolean).join(' · ') || '—'}</div>
          {lead.contact_name ? (
            <div className="contact-person" style={{ fontSize: '13px', marginTop: '4px', color: 'var(--text-muted)' }}>
              Ask for: <strong>{lead.contact_name}</strong> {lead.contact_title ? `(${lead.contact_title})` : ''}
            </div>
          ) : null}
        </div>
        <ScoreBadge score={lead.score} tier={lead.tier} />
      </div>
      <div className="tags">
        {lead.apply_count ? (
          <span className="badge hot">
            {lead.apply_count} applicant{lead.apply_count > 1 ? 's' : ''}
          </span>
        ) : null}
        {lead.roles_count ? (
          <span className="badge neutral">
            {lead.roles_count} role{lead.roles_count > 1 ? 's' : ''}
          </span>
        ) : null}
        {lead.role_group ? (
          <span className="badge neutral">
            {lead.role_group}
          </span>
        ) : null}
        {lead.last_disposition ? <DispositionPill disposition={lead.last_disposition} /> : null}
        {lead.next_action_date ? (
          <span className="badge sky">follow-up {fmtDate(lead.next_action_date)}</span>
        ) : null}
        {lead.source_query ? (
          <span className="badge neutral" title={lead.source_query}>
            {truncate(lead.source_query, 26)}
          </span>
        ) : null}
      </div>
    </Link>
  );
}
