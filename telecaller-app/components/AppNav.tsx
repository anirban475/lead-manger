'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/queue', label: 'Queue', ico: '📋' },
  { href: '/followups', label: 'Follow-ups', ico: '📞' },
  { href: '/stats', label: 'Stats', ico: '📊' },
];

export default function AppNav({
  displayName,
  logoutAction,
}: {
  displayName: string;
  logoutAction: () => Promise<void>;
}) {
  const path = usePathname();
  const isActive = (href: string) => path === href || path.startsWith(href + '/');

  return (
    <>
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" /> Cockpit
        </div>
        <nav>
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={`nav-link ${isActive(n.href) ? 'active' : ''}`}>
              <span className="ico">{n.ico}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="spacer" />
        <div className="who">
          <b>{displayName}</b>
          telecaller
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
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className={isActive(n.href) ? 'active' : ''}>
            <span className="ico">{n.ico}</span>
            {n.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
