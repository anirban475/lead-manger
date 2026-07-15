import { getFollowups } from '@/lib/queries';
import CallSheet from '@/components/CallSheet';

export const dynamic = 'force-dynamic';

export default async function FollowupsPage() {
  const leads = await getFollowups();
  return (
    <>
      <header className="topbar">
        <h1>Follow-ups due</h1>
        <span className="muted">{leads.length} today or overdue</span>
      </header>
      <div className="content" style={{ maxWidth: '100%' }}>
        <CallSheet leads={leads} isFollowupQueue={true} />
      </div>
    </>
  );
}
