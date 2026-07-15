'use client';

import { useState, useEffect } from 'react';
import { CleanPhone, normalizePhones } from '@/lib/phone';

export default function PhoneCell({ rawPhone }: { rawPhone: string | null | undefined }) {
  const [isMobile, setIsMobile] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    setIsMobile(window.matchMedia('(max-width: 768px)').matches);
  }, []);

  const phones = normalizePhones(rawPhone);

  if (phones.length === 0) {
    return <span className="text-muted" style={{ fontSize: '13px', fontStyle: 'italic' }}>needs enrichment</span>;
  }

  const handleCopy = async (e164: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(e164);
      setCopiedId(e164);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Failed to copy phone:', err);
    }
  };

  return (
    <div className="phone-cell-container" onClick={(e) => e.stopPropagation()}>
      {phones.map((phone, idx) => {
        const waLink = isMobile ? phone.waMobile : phone.waWeb;

        return (
          <div 
            key={phone.e164} 
            className="phone-row" 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              fontSize: '13px', 
              marginTop: idx > 0 ? '4px' : '0' 
            }}
          >
            {isMobile ? (
              <a href={phone.tel} className="phone-number-link tel-link" style={{ color: 'var(--color-primary-strong)', fontWeight: 600 }}>
                {phone.e164}
              </a>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', position: 'relative' }}>
                <span 
                  onClick={(e) => handleCopy(phone.e164, e)} 
                  className="phone-copy-text"
                  title="Click to copy E.164 number"
                  style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}
                >
                  {phone.e164}
                  {copiedId === phone.e164 && (
                    <span className="copy-toast-inline" style={{ marginLeft: '4px', color: 'var(--color-success)', fontSize: '11px', fontWeight: 'bold' }}>
                      Copied ✓
                    </span>
                  )}
                </span>
                <a href={phone.tel} className="icon-link btn-call-icon" title="Call via softphone" style={{ opacity: 0.7, fontSize: '12px' }}>
                  📞
                </a>
              </div>
            )}
            
            <a 
              href={waLink} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="icon-link btn-wa-icon" 
              title="Chat on WhatsApp"
              style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none', filter: 'grayscale(1)' }}
            >
              💬
            </a>
          </div>
        );
      })}
    </div>
  );
}
