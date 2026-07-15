'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import type { Lead } from '@/lib/queries';
import { FilterState } from '@/lib/savedFilters';
import FilterBar from './FilterBar';
import PhoneCell from './PhoneCell';
import LeadPanel from './LeadPanel';
import { ScoreBadge, DispositionPill } from './Badges';
import { fmtDate } from '@/lib/format';
import AddLeadForm from './AddLeadForm';
import CsvUploadModal from './CsvUploadModal';

export default function CallSheet({ leads, isFollowupQueue = false }: { leads: Lead[]; isFollowupQueue?: boolean }) {
  const router = useRouter();
  const [selectedLeadKey, setSelectedLeadKey] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCsvModal, setShowCsvModal] = useState(false);
  
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    tier: '',
    status: '',
    roleGroup: '',
    city: '',
    followupDue: isFollowupQueue, // default to true if in followup queue
  });

  const [isPending, startTransition] = useTransition();

  // Extract filter dropdown options
  const cities = Array.from(new Set(leads.map((l) => l.city).filter(Boolean))) as string[];
  const roleGroups = Array.from(new Set(leads.map((l) => l.role_group).filter(Boolean))) as string[];
  const statuses = Array.from(new Set(leads.map((l) => l.status).filter(Boolean))) as string[];

  // Filter leads in memory
  const todayStr = new Date().toISOString().split('T')[0];
  const filteredLeads = leads.filter((lead) => {
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const comp = (lead.company_name || lead.company_key).toLowerCase();
      const cont = (lead.contact_name || '').toLowerCase();
      if (!comp.includes(q) && !cont.includes(q)) return false;
    }
    if (filters.tier && lead.tier !== filters.tier) return false;
    if (filters.status && lead.status !== filters.status) return false;
    if (filters.roleGroup && lead.role_group !== filters.roleGroup) return false;
    if (filters.city && lead.city !== filters.city) return false;
    if (filters.followupDue) {
      if (!lead.next_action_date || lead.next_action_date > todayStr) return false;
    }
    return true;
  });

  const selectedLead = leads.find((l) => l.company_key === selectedLeadKey) || null;

  const handleRowClick = (lead: Lead) => {
    setSelectedLeadKey(lead.company_key);
  };

  const handleLeadUpdated = () => {
    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <div className="call-sheet-container" style={{ opacity: isPending ? 0.7 : 1, transition: 'opacity 0.2s ease' }}>
      <FilterBar
        filters={filters}
        onChange={setFilters}
        cities={cities.sort()}
        roleGroups={roleGroups.sort()}
        statuses={statuses.sort()}
      />

      <div className="sheet-summary-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
        <div className="sheet-summary text-muted" style={{ fontSize: '13px' }}>
          Showing <strong>{filteredLeads.length}</strong> of {leads.length} leads
          {isPending && <span style={{ marginLeft: '10px', fontSize: '11px', color: 'var(--color-primary-strong)', fontWeight: 'bold' }}>Refreshing list...</span>}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            className="btn ghost" 
            onClick={() => setShowCsvModal(true)} 
            style={{ padding: '6px 12px', fontSize: '13px' }}
          >
            ⬆ Import CSV
          </button>
          <button 
            className="btn primary" 
            onClick={() => setShowAddModal(true)} 
            style={{ padding: '6px 12px', fontSize: '13px' }}
          >
            + Add Lead
          </button>
        </div>
      </div>

      {filteredLeads.length === 0 ? (
        <div className="empty card pad" style={{ textAlign: 'center', padding: '40px' }}>
          No leads match the current filters.
        </div>
      ) : (
        <>
          {/* Desktop Table View */}
          <div className="table-responsive desktop-only">
            <table className="dense-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: '80px', textAlign: 'left' }}>Tier/Score</th>
                  <th style={{ textAlign: 'left' }}>Company</th>
                  <th style={{ textAlign: 'left' }}>Contact Person</th>
                  <th style={{ textAlign: 'left' }}>Phone Numbers</th>
                  <th style={{ width: '100px', textAlign: 'center' }}>Applicants</th>
                  <th style={{ textAlign: 'left' }}>Last Outcome</th>
                  <th style={{ textAlign: 'left' }}>Follow-up</th>
                  <th style={{ width: '80px', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredLeads.map((lead) => (
                  <tr 
                    key={lead.company_key} 
                    onClick={() => handleRowClick(lead)}
                    className="row-hover-highlight"
                    style={{ cursor: 'pointer', borderBottom: '1px solid var(--border-default)' }}
                  >
                    <td style={{ padding: '8px' }}>
                      <ScoreBadge score={lead.score} tier={lead.tier} />
                    </td>
                    <td style={{ padding: '8px' }}>
                      <div className="table-co-name" style={{ fontWeight: 600, color: 'var(--text-strong)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {lead.company_name || lead.company_key}
                        {lead.origin === 'manual' && (
                          <span className="badge neutral" style={{ fontSize: '10px', padding: '2px 4px', fontWeight: 'normal', textTransform: 'lowercase' }}>
                            manual
                          </span>
                        )}
                      </div>
                      <div className="table-co-meta text-muted" style={{ fontSize: '11px', marginTop: '2px' }}>
                        {[lead.city, lead.role_group, lead.industry_label].filter(Boolean).join(' · ') || '—'}
                      </div>
                    </td>
                    <td style={{ padding: '8px' }}>
                      {lead.contact_name ? (
                        <>
                          <div style={{ fontWeight: 500, fontSize: '13px' }}>{lead.contact_name}</div>
                          {lead.contact_title && (
                            <div className="text-muted" style={{ fontSize: '11px' }}>{lead.contact_title}</div>
                          )}
                        </>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '12px', fontStyle: 'italic' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '8px' }}>
                      <PhoneCell rawPhone={lead.contact_phone} />
                    </td>
                    <td style={{ textAlign: 'center', padding: '8px' }}>
                      {lead.apply_count ? (
                        <span className="badge hot" style={{ fontSize: '11px' }}>
                          🔥 {lead.apply_count}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td style={{ padding: '8px' }}>
                      {lead.last_disposition ? (
                        <DispositionPill disposition={lead.last_disposition} />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td style={{ padding: '8px' }}>
                      {lead.next_action_date ? (
                        <span className="badge sky" style={{ fontSize: '11px' }}>
                          {fmtDate(lead.next_action_date)}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'center', padding: '8px' }}>
                      <button 
                        className="btn primary" 
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRowClick(lead);
                        }}
                      >
                        Log
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Stacked Card View */}
          <div className="mobile-only lead-list">
            {filteredLeads.map((lead) => (
              <div 
                key={lead.company_key} 
                onClick={() => handleRowClick(lead)} 
                className="card pad lead-card"
                style={{ cursor: 'pointer', padding: '12px' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%', marginBottom: '8px' }}>
                  <div style={{ flex: 1, paddingRight: '8px' }}>
                    <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-strong)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {lead.company_name || lead.company_key}
                      {lead.origin === 'manual' && (
                        <span className="badge neutral" style={{ fontSize: '10px', padding: '2px 4px', fontWeight: 'normal', textTransform: 'lowercase' }}>
                          manual
                        </span>
                      )}
                    </div>
                    <div className="text-muted" style={{ fontSize: '12px', marginTop: '2px' }}>
                      {[lead.city, lead.role_group].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <ScoreBadge score={lead.score} tier={lead.tier} />
                </div>

                {lead.contact_name && (
                  <div style={{ fontSize: '13px', margin: '4px 0 8px 0' }}>
                    👤 Ask for: <strong>{lead.contact_name}</strong> {lead.contact_title ? `(${lead.contact_title})` : ''}
                  </div>
                )}

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                  {lead.apply_count ? <span className="badge hot" style={{ fontSize: '11px' }}>🚨 {lead.apply_count}</span> : null}
                  {lead.last_disposition ? <DispositionPill disposition={lead.last_disposition} /> : null}
                  {lead.next_action_date ? <span className="badge sky" style={{ fontSize: '11px' }}>due {fmtDate(lead.next_action_date)}</span> : null}
                </div>

                <div style={{ display: 'flex', gap: '8px', marginTop: '8px', borderTop: '1px solid var(--border-default)', paddingTop: '8px', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <PhoneCell rawPhone={lead.contact_phone} />
                  </div>
                  <button 
                    className="btn primary" 
                    style={{ padding: '6px 16px', fontSize: '13px' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRowClick(lead);
                    }}
                  >
                    Log
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Slide-over Drawer Panel */}
      <LeadPanel 
        lead={selectedLead} 
        onClose={() => setSelectedLeadKey(null)}
        onLeadUpdated={handleLeadUpdated}
      />

      {showAddModal && (
        <AddLeadForm 
          onClose={() => setShowAddModal(false)} 
          onSuccess={handleLeadUpdated} 
        />
      )}

      {showCsvModal && (
        <CsvUploadModal 
          onClose={() => setShowCsvModal(false)} 
          onSuccess={handleLeadUpdated} 
        />
      )}
    </div>
  );
}
