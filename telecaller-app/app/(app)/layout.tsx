import { redirect } from 'next/navigation';
import { getSession, canSeeTeam } from '@/lib/auth';
import { logout } from '@/actions/auth';
import AppNav from '@/components/AppNav';

export const dynamic = 'force-dynamic';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) redirect('/login');

  return (
    <div className="app-shell">
      <AppNav
        displayName={session.displayName}
        role={session.role}
        isAdmin={session.role === 'admin'}
        canSeeTeam={canSeeTeam(session.role)}
        logoutAction={logout}
      />
      <div className="main">{children}</div>
    </div>
  );
}

