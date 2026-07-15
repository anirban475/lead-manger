import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';
import LoginForm from '@/components/LoginForm';

export const dynamic = 'force-dynamic';

export default async function LoginPage() {
  const session = await getSession();
  if (session) redirect('/queue');

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div
          className="brand"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: 'var(--text-strong)',
            fontWeight: 700,
            fontSize: 18,
            marginBottom: 16,
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-primary)' }} />
          Telecaller Cockpit
        </div>
        <h1>Sign in</h1>
        <p className="sub">Jobdrive lead telecalling</p>
        <LoginForm />
      </div>
    </div>
  );
}
