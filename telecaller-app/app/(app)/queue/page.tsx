import { getQueue } from '@/lib/queries';
import CallSheet from '@/components/CallSheet';

export const dynamic = 'force-dynamic';

export default async function QueuePage() {
  const leads = await getQueue();

  return (
    <>
      <header className="topbar">
        <h1>Lead Queue</h1>
        <span className="muted">{leads.length} active leads</span>
      </header>
      <div className="content" style={{ maxWidth: '100%' }}>
        <CallSheet leads={leads} />
      </div>
    </>
  );
}
