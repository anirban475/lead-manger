import { getFollowups } from '@/lib/queries';
import { getSession } from '@/lib/auth';
import CallSheet from '@/components/CallSheet';

export const dynamic = 'force-dynamic';

export default async function FollowupsPage() {
  const session = await getSession();
  if (!session) return null;
  const leads = await getFollowups(session.email);
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
