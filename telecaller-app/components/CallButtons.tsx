'use client';

import { useState, useEffect } from 'react';
import { normalizePhones } from '@/lib/phone';

export default function CallButtons({ phone, size }: { phone: string | null; size?: 'lg' }) {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    setIsDesktop(!/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent));
  }, []);

  const list = normalizePhones(phone);
  if (list.length === 0) return <span className="badge warn">needs enrichment</span>;
  const lg = size === 'lg' ? ' lg' : '';

  return (
    <div className="stack" style={{ gap: '8px' }}>
      {list.map((p) => (
        <div key={p.e164} className="call-row" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* tel: opens the dialer on mobile — one-tap dial */}
          <a className={`btn call${lg}`} href={p.tel}>📞 Call {p.e164}</a>
          <a
            className={`btn wa${lg}`}
            href={isDesktop ? p.waWeb : p.waMobile}
            target="_blank"
            rel="noopener noreferrer"
          >
            WhatsApp
          </a>
          {p.lowConfidence ? <span className="badge warn">check number</span> : null}
        </div>
      ))}
    </div>
  );
}
