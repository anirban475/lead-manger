'use client';

import { useState, useEffect, useTransition, useRef } from 'react';
import type { Lead, TimelineItem } from '@/lib/queries';
import { DISPOSITION_META, DISPOSITION_GROUPS, NEEDS_FOLLOWUP, type Disposition } from '@/lib/dispositions';
import { logCall } from '@/actions/logCall';
import { addComment } from '@/actions/addComment';
import { getLeadActivityAction } from '@/actions/getLeadActivity';
import { updateLeadContact } from '@/actions/updateLeadContact';
import PhoneCell from './PhoneCell';
import { ScoreBadge, TierBadge, DispositionPill, StatusBadge } from './Badges';
import { fmtDate, fmtDateTime } from '@/lib/format';

type LeadPanelProps = {
  lead: Lead | null;
  onClose: () => void;
  onLeadUpdated?: () => void;
};

export default function LeadPanel({ lead, onClose, onLeadUpdated }: LeadPanelProps) {
  const [activity, setActivity] = useState<TimelineItem[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [selectedDisposition, setSelectedDisposition] = useState<Disposition | ''>('');
  const [commentText, setCommentText] = useState('');
  const [isPending, startTransition] = useTransition();
  const [isEditingContact, setIsEditingContact] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editPending, startEditTransition] = useTransition();
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Load activity when lead changes
  useEffect(() => {
    if (!lead) {
      setActivity([]);
      setSelectedDisposition('');
      setCommentText('');
      setIsEditingContact(false);
      setEditError(null);
      return;
    }

    setIsEditingContact(false);
    setEditError(null);
    setLoadingActivity(true);
    getLeadActivityAction(lead.company_key)
      .then((data) => {
        setActivity(data);
      })
      .catch((err) => console.error('Failed to load activity:', err))
      .finally(() => setLoadingActivity(false));

    setSelectedDisposition((lead.last_disposition as Disposition) || '');
  }, [lead]);

  if (!lead) return null;

  const handleLogCallSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedDisposition) return;

    const formData = new FormData(e.currentTarget);
    formData.append('company_key', lead.company_key);
    formData.append('disposition', selectedDisposition);
    formData.append('no_redirect', 'true');

    startTransition(async () => {
      try {
        await logCall(formData);
        // Reload activity
        const updated = await getLeadActivityAction(lead.company_key);
        setActivity(updated);
        if (onLeadUpdated) onLeadUpdated();
      } catch (err) {
        console.error('Failed to log call:', err);
        alert('Failed to log call outcome.');
      }
    });
  };

  const handleAddCommentSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    const formData = new FormData();
    formData.append('company_key', lead.company_key);
    formData.append('body', commentText.trim());

    startTransition(async () => {
      try {
        await addComment(formData);
        setCommentText('');
        // Reload activity
        const updated = await getLeadActivityAction(lead.company_key);
        setActivity(updated);
        if (onLeadUpdated) onLeadUpdated();
      } catch (err) {
        console.error('Failed to add comment:', err);
        alert('Failed to post comment.');
      }
    });
  };

  const handleEditSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setEditError(null);
    const formData = new FormData(e.currentTarget);
    formData.append('company_key', lead.company_key);

    startEditTransition(async () => {
      try {
        const res = await updateLeadContact(formData);
        if (res.success) {
          setIsEditingContact(false);
          if (onLeadUpdated) onLeadUpdated();
        } else {
          setEditError(res.error || 'Failed to update contact');
        }
      } catch (err: any) {
        setEditError(err.message || 'An unexpected error occurred');
      }
    });
  };

  const showFollowUpInput = selectedDisposition && NEEDS_FOLLOWUP.includes(selectedDisposition);

  return (
    <>
      {/* Backdrop for click-out and blur effect */}
      <div className="drawer-backdrop active" onClick={onClose} />
      
      <div className="drawer active" ref={panelRef}>
        <header className="drawer-header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%' }}>
            <div style={{ flex: 1, paddingRight: '12px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, margin: 0 }}>
                {lead.company_name || lead.company_key}
              </h2>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px', alignItems: 'center' }}>
                <TierBadge tier={lead.tier} />
                <StatusBadge status={lead.status} />
                {lead.last_disposition ? <DispositionPill disposition={lead.last_disposition} /> : null}
              </div>
            </div>
            <button className="drawer-close" onClick={onClose} aria-label="Close panel">
              ✕
            </button>
          </div>
        </header>

        <div className="drawer-body">
          {/* Section 1: Quick Contacts */}
          <div className="drawer-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Contact Information</div>
              {!isEditingContact && (
                <button 
                  type="button" 
                  onClick={() => setIsEditingContact(true)} 
                  style={{ background: 'transparent', border: 'none', color: 'var(--color-primary-strong)', fontSize: '12px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
                >
                  ✎ Edit
                </button>
              )}
            </div>

            {isEditingContact ? (
              <form onSubmit={handleEditSubmit} className="card pad animate-fade-in" style={{ border: '1px solid var(--border-default)', padding: '12px', background: 'var(--surface-sunken)' }}>
                {editError && <div className="form-error" style={{ marginBottom: '8px', fontSize: '12px' }}>⚠️ {editError}</div>}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div>
                    <label htmlFor="edit_phone" style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '2px' }}>Phone Number(s) *</label>
                    <input type="text" id="edit_phone" name="contact_phone" className="input" defaultValue={lead.contact_phone || ''} required style={{ padding: '6px 10px', fontSize: '13px' }} />
                  </div>
                  <div>
                    <label htmlFor="edit_email" style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '2px' }}>Email Address</label>
                    <input type="email" id="edit_email" name="contact_email" className="input" defaultValue={lead.contact_email && lead.contact_email !== '-' ? lead.contact_email : ''} style={{ padding: '6px 10px', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <label htmlFor="edit_name" style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '2px' }}>Ask for Name</label>
                      <input type="text" id="edit_name" name="contact_name" className="input" defaultValue={lead.contact_name || ''} style={{ padding: '6px 10px', fontSize: '13px' }} />
                    </div>
                    <div>
                      <label htmlFor="edit_title" style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '2px' }}>Title</label>
                      <input type="text" id="edit_title" name="contact_title" className="input" defaultValue={lead.contact_title || ''} style={{ padding: '6px 10px', fontSize: '13px' }} />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <button type="button" onClick={() => setIsEditingContact(false)} className="btn secondary" style={{ flex: 1, padding: '6px 10px', fontSize: '12px' }}>Cancel</button>
                    <button type="submit" className="btn primary" style={{ flex: 1, padding: '6px 10px', fontSize: '12px' }} disabled={editPending}>{editPending ? 'Saving...' : 'Save Fix'}</button>
                  </div>
                </div>
              </form>
            ) : (
              <>
                <div style={{ marginBottom: '12px' }}>
                  {lead.contact_name ? (
                    <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-strong)' }}>
                      👤 Ask for: <span style={{ color: 'var(--color-primary-strong)' }}>{lead.contact_name}</span>
                      {lead.contact_title ? <span className="text-muted" style={{ fontWeight: 500, fontSize: '13px' }}> · {lead.contact_title}</span> : ''}
                    </div>
                  ) : (
                    <div className="text-muted" style={{ fontSize: '14px', fontStyle: 'italic' }}>No contact name listed</div>
                  )}
                </div>

                {lead.apply_count ? (
                  <div style={{ marginBottom: '12px' }}>
                    <span className="badge hot" style={{ fontSize: '13px', padding: '3px 8px' }}>
                      🚨 {lead.apply_count} applicants (High Demand)
                    </span>
                  </div>
                ) : null}

                <div className="card pad" style={{ background: 'var(--surface-sunken)', border: 'none', padding: '12px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>Dial/Copy Phone</div>
                  <PhoneCell rawPhone={lead.contact_phone} />
                </div>
              </>
            )}
          </div>

          {/* Section 2: Log call outcome */}
          <div className="drawer-section card pad" style={{ border: '1px solid var(--border-default)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '12px' }}>Log Call Outcome</h3>
            
            <form onSubmit={handleLogCallSubmit}>
              <div className="disposition-groups" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {DISPOSITION_GROUPS.map((group) => (
                  <div key={group.key}>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                      {group.label}
                    </div>
                    <div className="disposition-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {Object.entries(DISPOSITION_META)
                        .filter(([_, meta]) => meta.group === group.key)
                        .map(([dispKey, meta]) => {
                          const isSelected = selectedDisposition === dispKey;
                          return (
                            <button
                              key={dispKey}
                              type="button"
                              onClick={() => setSelectedDisposition(dispKey as Disposition)}
                              className={`badge ${meta.tone} ${isSelected ? 'active-chip' : ''}`}
                              style={{
                                cursor: 'pointer',
                                border: isSelected ? '2px solid var(--text-strong)' : '1px solid transparent',
                                opacity: isSelected ? 1 : 0.8,
                                padding: '6px 12px',
                                fontSize: '12px',
                                display: 'inline-flex',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {meta.label}
                            </button>
                          );
                        })}
                    </div>
                  </div>
                ))}
              </div>

              {selectedDisposition && (
                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }} className="animate-fade-in">
                  {showFollowUpInput && (
                    <div>
                      <label htmlFor="follow_up_date" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                        Follow-up Date
                      </label>
                      <input
                        type="date"
                        id="follow_up_date"
                        name="follow_up_date"
                        className="input"
                        required
                        defaultValue={new Date(Date.now() + 86400000).toISOString().split('T')[0]} // tomorrow
                      />
                    </div>
                  )}

                  <div>
                    <label htmlFor="notes" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                      Notes / Remarks
                    </label>
                    <textarea
                      id="notes"
                      name="notes"
                      className="input"
                      placeholder="Add conversation notes or reason for failure..."
                      rows={2}
                      style={{ resize: 'vertical', width: '100%', minHeight: '60px' }}
                    />
                  </div>

                  <button type="submit" disabled={isPending} className="btn primary block">
                    {isPending ? 'Saving...' : 'Save Call Outcome'}
                  </button>
                </div>
              )}
            </form>
          </div>

          {/* Section 3: Add Comment */}
          <div className="drawer-section card pad" style={{ border: '1px solid var(--border-default)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px' }}>Add Comment / Freeform Note</h3>
            <form onSubmit={handleAddCommentSubmit}>
              <textarea
                className="input"
                placeholder="Type a quick comment (adds to timeline instantly)..."
                required
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={2}
                style={{ resize: 'vertical', width: '100%', minHeight: '60px', marginBottom: '8px' }}
              />
              <button type="submit" disabled={isPending || !commentText.trim()} className="btn secondary block">
                {isPending ? 'Posting...' : 'Post Comment'}
              </button>
            </form>
          </div>

          {/* Section 4: Timeline activity history */}
          <div className="drawer-section">
            <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '12px' }}>Activity History</h3>
            
            {loadingActivity ? (
              <div className="text-muted" style={{ textAlign: 'center', padding: '16px', fontSize: '13px' }}>
                Loading activity feed...
              </div>
            ) : activity.length === 0 ? (
              <div className="text-muted" style={{ textAlign: 'center', padding: '16px', fontSize: '13px', fontStyle: 'italic' }}>
                No activity logged yet.
              </div>
            ) : (
              <div className="stack" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {activity.map((item) => {
                  if (item.type === 'call') {
                    const c = item.data;
                    return (
                      <div key={`call-${c.id}`} className="call-log-item card pad" style={{ padding: '10px', fontSize: '13px', border: '1px solid var(--border-default)' }}>
                        <div className="rowspread" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <span style={{ fontSize: '12px' }}>📞</span>
                            <DispositionPill disposition={c.disposition} />
                          </div>
                          <span className="faint" style={{ fontSize: '11px' }}>{fmtDateTime(c.called_at)}</span>
                        </div>
                        {c.notes ? <div style={{ marginTop: '6px', fontWeight: 500 }}>{c.notes}</div> : null}
                        <div className="faint" style={{ marginTop: '4px', fontSize: '11px' }}>
                          Logged by {c.caller}
                          {c.follow_up_date ? ` · follow-up ${fmtDate(c.follow_up_date)}` : ''}
                        </div>
                      </div>
                    );
                  } else {
                    const cm = item.data;
                    return (
                      <div 
                        key={`comment-${cm.id}`} 
                        className="call-log-item card pad" 
                        style={{ 
                          padding: '10px', 
                          fontSize: '13px', 
                          borderLeft: '3px solid var(--color-primary-strong)', 
                          borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
                          borderTop: '1px solid var(--border-default)',
                          borderRight: '1px solid var(--border-default)',
                          borderBottom: '1px solid var(--border-default)'
                        }}
                      >
                        <div className="rowspread" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 700, fontSize: '12px', color: 'var(--text-strong)' }}>
                            💬 Comment by {cm.author}
                          </span>
                          <span className="faint" style={{ fontSize: '11px' }}>{fmtDateTime(cm.created_at)}</span>
                        </div>
                        <div style={{ marginTop: '6px', whiteSpace: 'pre-wrap' }}>{cm.body}</div>
                      </div>
                    );
                  }
                })}
              </div>
            )}
          </div>

          {/* Section 5: Meta fields details list */}
          <div className="drawer-section">
            <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px' }}>Lead Facts</h3>
            <dl className="kv" style={{ fontSize: '13px', margin: 0 }}>
              <dt>City</dt>
              <dd>{lead.city || '—'}</dd>
              <dt>Industry</dt>
              <dd>{lead.industry_label || lead.industry || '—'}</dd>
              <dt>Company Size</dt>
              <dd>{lead.size || '—'}</dd>
              <dt>Email</dt>
              <dd>{lead.contact_email && lead.contact_email !== '-' ? lead.contact_email : '—'}</dd>
              <dt>Website</dt>
              <dd>
                {lead.company_website ? (
                  <a href={lead.company_website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary-strong)', textDecoration: 'underline' }}>
                    {lead.company_website}
                  </a>
                ) : '—'}
              </dd>
              <dt>Roles Found</dt>
              <dd>{lead.role_titles?.length ? lead.role_titles.join(', ') : (lead.roles_count ?? '—')}</dd>
              <dt>Scrape Query</dt>
              <dd>{lead.source_query || '—'}</dd>
              <dt>Next Action</dt>
              <dd>
                {lead.next_action || '—'}
                {lead.next_action_date ? ` (${fmtDate(lead.next_action_date)})` : ''}
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </>
  );
}
