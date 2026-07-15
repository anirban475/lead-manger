'use client';

import { useState, useTransition } from 'react';
import { createLead } from '@/actions/createLead';

type AddLeadFormProps = {
  onClose: () => void;
  onSuccess: () => void;
};

export default function AddLeadForm({ onClose, onSuccess }: AddLeadFormProps) {
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const formData = new FormData(e.currentTarget);

    startTransition(async () => {
      try {
        const res = await createLead(formData);
        if (res.success) {
          onSuccess();
          onClose();
        } else {
          setError(res.error || 'Failed to add lead.');
        }
      } catch (err: any) {
        setError(err.message || 'An unexpected error occurred.');
      }
    });
  };

  return (
    <>
      <div className="drawer-backdrop active" onClick={onClose} style={{ zIndex: 110 }} />
      <div
        className="card pad"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '90%',
          maxWidth: '460px',
          maxHeight: '90vh',
          overflowY: 'auto',
          zIndex: 120,
          background: 'var(--surface-card)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
          border: '1px solid var(--border-default)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Add New Lead</h2>
          <button 
            type="button" 
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '20px',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              padding: '4px'
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="form-error animate-fade-in" style={{ padding: '8px 12px', background: 'var(--color-danger-bg)', borderRadius: 'var(--radius-sm)', marginBottom: '12px' }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label htmlFor="company_name" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              Company Name *
            </label>
            <input 
              type="text" 
              id="company_name" 
              name="company_name" 
              className="input" 
              required 
              placeholder="e.g. Acme Corporation" 
            />
          </div>

          <div>
            <label htmlFor="contact_phone" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              Phone Number(s) *
            </label>
            <input 
              type="text" 
              id="contact_phone" 
              name="contact_phone" 
              className="input" 
              required 
              placeholder="e.g. +91 98765 43210, +91 99999 88888" 
            />
            <span className="text-muted" style={{ fontSize: '11px', marginTop: '2px', display: 'block' }}>
              Separate multiple numbers with commas.
            </span>
          </div>

          <div>
            <label htmlFor="contact_email" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              Email Address
            </label>
            <input 
              type="email" 
              id="contact_email" 
              name="contact_email" 
              className="input" 
              placeholder="e.g. hr@acme.com" 
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label htmlFor="contact_name" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Contact Person
              </label>
              <input 
                type="text" 
                id="contact_name" 
                name="contact_name" 
                className="input" 
                placeholder="e.g. John Doe" 
              />
            </div>
            <div>
              <label htmlFor="contact_title" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Title / Designation
              </label>
              <input 
                type="text" 
                id="contact_title" 
                name="contact_title" 
                className="input" 
                placeholder="e.g. HR Manager" 
              />
            </div>
          </div>

          <div>
            <label htmlFor="city" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              City
            </label>
            <input 
              type="text" 
              id="city" 
              name="city" 
              className="input" 
              placeholder="e.g. Mumbai" 
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
            <button 
              type="button" 
              onClick={onClose} 
              className="btn secondary" 
              style={{ flex: 1 }}
              disabled={isPending}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn primary" 
              style={{ flex: 1 }}
              disabled={isPending}
            >
              {isPending ? 'Saving...' : 'Add Lead'}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
