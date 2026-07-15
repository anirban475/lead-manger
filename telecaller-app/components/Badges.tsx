import { DISPOSITION_META, type Disposition } from '@/lib/dispositions';

export function ScoreBadge({ score, tier }: { score: number | null; tier: string | null }) {
  const cls = tier === 'hot' ? 'hot' : tier === 'warm' ? 'warm' : 'neutral';
  return (
    <span className={`badge ${cls} score-badge`}>
      <span className="n">{score ?? '—'}</span>
      {tier ?? ''}
    </span>
  );
}

export function TierBadge({ tier }: { tier: string | null }) {
  if (!tier) return null;
  return <span className={`badge ${tier === 'hot' ? 'hot' : 'warm'}`}>{tier}</span>;
}

export function DispositionPill({ disposition }: { disposition: string | null }) {
  if (!disposition) return null;
  const meta = DISPOSITION_META[disposition as Disposition];
  return <span className={`badge ${meta?.tone ?? 'neutral'}`}>{meta?.label ?? disposition}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className="badge neutral">{status.replace(/_/g, ' ')}</span>;
}
