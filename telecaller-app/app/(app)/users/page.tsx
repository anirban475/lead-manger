import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';
import { query } from '@/lib/db';
import { listUsers } from '@/lib/users';
import UsersAdmin from '@/components/UsersAdmin';

export const dynamic = 'force-dynamic';

export default async function UsersPage() {
  const session = await getSession();
  if (!session) {
    redirect('/queue');
  }

  const rows = await query<{ email: string; role: string; is_active: boolean }>(
    'SELECT email, role, is_active FROM app_users WHERE email = $1 AND role = $2 AND is_active = true',
    [session.email.toLowerCase().trim(), 'admin'],
  );
  if (!rows || rows.length === 0) {
    redirect('/queue');
  }

  const users = await listUsers();

  return (
    <>
      <header className="topbar">
        <h1>User Management</h1>
        <span className="muted">{users.length} users</span>
      </header>
      <div className="content">
        <UsersAdmin users={users} currentEmail={session.email} />
      </div>
    </>
  );
}
