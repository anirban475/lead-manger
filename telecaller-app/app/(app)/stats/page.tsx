import { getDispositionCounts, getQueryConversion } from '@/lib/queries';
import { DISPOSITION_META, type Disposition } from '@/lib/dispositions';

export const dynamic = 'force-dynamic';

export default async function StatsPage() {
  const [dispositions, conversion] = await Promise.all([getDispositionCounts(), getQueryConversion()]);
  const total = dispositions.reduce((sum, d) => sum + parseInt(d.n, 10), 0);

  return (
    <>
      <header className="topbar">
        <h1>Stats &amp; feedback</h1>
        <span className="muted">{total} calls logged</span>
      </header>
      <div className="content stack">
        <div className="card pad">
          <div className="section-title">Call outcomes</div>
          {dispositions.length === 0 ? (
            <div className="muted">No calls logged yet.</div>
          ) : (
            <div className="stat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 12 }}>
              {dispositions.map((d) => (
                <div key={d.disposition} className="card pad" style={{ boxShadow: 'none' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-strong)' }}>{d.n}</div>
                  <div className="badge" style={{ marginTop: 4 }}>
                    <span className={`badge ${DISPOSITION_META[d.disposition as Disposition]?.tone ?? 'neutral'}`}>
                      {DISPOSITION_META[d.disposition as Disposition]?.label ?? d.disposition}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card pad">
          <div className="section-title">Conversion by source query</div>
          <p className="muted" style={{ marginTop: -6, marginBottom: 12, fontSize: 13 }}>
            The learning signal the scraper reads — which queries produce leads that actually convert on the phone.
          </p>
          {conversion.length === 0 ? (
            <div className="muted">No data yet.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 620 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', fontSize: 12 }}>
                    <th style={{ padding: '8px 10px' }}>Source query</th>
                    <th style={{ padding: '8px 10px' }}>Cos</th>
                    <th style={{ padding: '8px 10px' }}>Hot</th>
                    <th style={{ padding: '8px 10px' }}>Contacted</th>
                    <th style={{ padding: '8px 10px' }}>Interested</th>
                    <th style={{ padding: '8px 10px' }}>Converted</th>
                    <th style={{ padding: '8px 10px' }}>Registered</th>
                    <th style={{ padding: '8px 10px' }}>Positive cos</th>
                  </tr>
                </thead>
                <tbody>
                  {conversion.map((r, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--border-default)' }}>
                      <td style={{ padding: '8px 10px', color: 'var(--text-strong)' }}>{r.source_query}</td>
                      <td style={{ padding: '8px 10px' }}>{r.companies}</td>
                      <td style={{ padding: '8px 10px' }}>{r.hot_companies}</td>
                      <td style={{ padding: '8px 10px' }}>{r.contacted_companies}</td>
                      <td style={{ padding: '8px 10px' }}>{r.interested_calls}</td>
                      <td style={{ padding: '8px 10px' }}>{r.converted_calls}</td>
                      <td style={{ padding: '8px 10px' }}>{r.registered_calls}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700 }}>{r.positive_companies}</td>
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
