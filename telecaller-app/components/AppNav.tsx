'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const BASE_NAV = [
  { href: '/queue', label: 'Queue', ico: '📋' },
  { href: '/followups', label: 'Follow-ups', ico: '📞' },
  { href: '/performance', label: 'Performance', ico: '📈' },
  { href: '/stats', label: 'Stats', ico: '📊' },
];

export default function AppNav({
  displayName,
  role = 'caller',
  isAdmin = false,
  canSeeTeam = false,
  logoutAction,
}: {
  displayName: string;
  role?: string;
  isAdmin?: boolean;
  canSeeTeam?: boolean;
  logoutAction: () => Promise<void>;
}) {
  const path = usePathname();
  const isActive = (href: string) => path === href || path.startsWith(href + '/');
  const navItems = isAdmin
    ? [...BASE_NAV, { href: '/users', label: 'Users', ico: '👥' }]
    : BASE_NAV;

  return (
    <>
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" /> Cockpit
        </div>
        <nav>
          {navItems.map((n) => (
            <Link key={n.href} href={n.href} className={`nav-link ${isActive(n.href) ? 'active' : ''}`}>
              <span className="ico">{n.ico}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="spacer" />
        <div className="who">
          <b>{displayName}</b>
          {role}
        </div>
        <form action={logoutAction}>
          <button
            type="submit"
            className="nav-link"
            style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', font: 'inherit' }}
          >
            <span className="ico">⏻</span>Sign out
          </button>
        </form>
      </aside>

      <nav className="mobile-tabbar">
        {navItems.map((n) => (
          <Link key={n.href} href={n.href} className={isActive(n.href) ? 'active' : ''}>
            <span className="ico">{n.ico}</span>
            {n.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
