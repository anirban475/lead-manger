'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import type { AppUser } from '@/lib/users';
import { fmtDate } from '@/lib/format';
import { createUser } from '@/actions/createUser';
import { resetUserPassword } from '@/actions/resetUserPassword';
import { setUserActive } from '@/actions/setUserActive';

type UsersAdminProps = {
  users: AppUser[];
  currentEmail: string;
};

export default function UsersAdmin({ users, currentEmail }: UsersAdminProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [showAddModal, setShowAddModal] = useState(false);
  const [resetTargetUser, setResetTargetUser] = useState<AppUser | null>(null);

  const [addError, setAddError] = useState<string | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const isSelf = (user: AppUser) =>
    user.email.toLowerCase().trim() === currentEmail.toLowerCase().trim();

  const handleAddSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setAddError(null);
    const formData = new FormData(e.currentTarget);

    startTransition(async () => {
      try {
        const res = await createUser(formData);
        if (res.success) {
          setShowAddModal(false);
          router.refresh();
        } else {
          setAddError(res.error || 'Failed to create user.');
        }
      } catch (err: any) {
        setAddError(err.message || 'An unexpected error occurred.');
      }
    });
  };

  const handleResetSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!resetTargetUser) return;
    setResetError(null);
    const formData = new FormData(e.currentTarget);
    const newPassword = String(formData.get('password') || '');

    startTransition(async () => {
      try {
        const res = await resetUserPassword(resetTargetUser.id, newPassword);
        if (res.success) {
          setResetTargetUser(null);
          router.refresh();
        } else {
          setResetError(res.error || 'Failed to reset password.');
        }
      } catch (err: any) {
        setResetError(err.message || 'An unexpected error occurred.');
      }
    });
  };

  const handleToggleActive = (user: AppUser) => {
    if (isSelf(user)) return;
    setActionError(null);
    startTransition(async () => {
      try {
        const res = await setUserActive(user.id, !user.is_active);
        if (res.success) {
          router.refresh();
        } else {
          setActionError(res.error || 'Failed to update user status.');
        }
      } catch (err: any) {
        setActionError(err.message || 'An unexpected error occurred.');
      }
    });
  };

  return (
    <div className="stack">
      <div className="rowspread" style={{ marginBottom: '8px' }}>
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Team Accounts</h2>
          <span className="muted" style={{ fontSize: '13px' }}>
            Manage access, roles, and credentials for telecallers and administrators.
          </span>
        </div>
        <button
          type="button"
          className="btn primary"
          onClick={() => {
            setAddError(null);
            setShowAddModal(true);
          }}
        >
          + Add User
        </button>
      </div>

      {actionError && (
        <div
          className="form-error"
          style={{
            padding: '8px 12px',
            background: 'var(--color-danger-bg)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          ⚠️ {actionError}
        </div>
      )}

      <div className="table-responsive">
        <table className="dense-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const self = isSelf(u);
              return (
                <tr key={u.id} className="row-hover-highlight">
                  <td style={{ fontWeight: 600 }}>{u.display_name || '—'}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`badge ${u.role === 'admin' ? 'sky' : 'neutral'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    {u.is_active ? (
                      <span className="badge good">Active</span>
                    ) : (
                      <span className="badge bad">Inactive</span>
                    )}
                  </td>
                  <td className="muted">{fmtDate(u.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        className="btn ghost"
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                        disabled={isPending}
                        onClick={() => {
                          setResetError(null);
                          setResetTargetUser(u);
                        }}
                        title={self ? 'Reset your own password' : 'Reset password'}
                      >
                        Reset password
                      </button>
                      <button
                        type="button"
                        className="btn ghost"
                        style={{
                          padding: '4px 10px',
                          fontSize: '12px',
                          color: u.is_active ? 'var(--color-danger)' : 'var(--color-success)',
                        }}
                        disabled={self || isPending}
                        onClick={() => handleToggleActive(u)}
                        title={self ? 'You cannot deactivate your own account' : u.is_active ? 'Deactivate account' : 'Reactivate account'}
                      >
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <>
          <div
            className="drawer-backdrop active"
            onClick={() => setShowAddModal(false)}
            style={{ zIndex: 110 }}
          />
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
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px',
              }}
            >
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Add New User</h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {addError && (
              <div
                className="form-error"
                style={{
                  padding: '8px 12px',
                  background: 'var(--color-danger-bg)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '12px',
                }}
              >
                ⚠️ {addError}
              </div>
            )}

            <form onSubmit={handleAddSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label
                  htmlFor="display_name"
                  style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}
                >
                  Name *
                </label>
                <input
                  type="text"
                  id="display_name"
                  name="display_name"
                  className="input"
                  required
                  placeholder="e.g. Jane Doe"
                />
              </div>

              <div>
                <label
                  htmlFor="email"
                  style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}
                >
                  Email *
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  className="input"
                  required
                  placeholder="e.g. jane@amatec.in"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}
                >
                  Password * (min 8 characters)
                </label>
                <input
                  type="password"
                  id="password"
                  name="password"
                  className="input"
                  required
                  minLength={8}
                  placeholder="••••••••"
                />
              </div>

              <div>
                <label
                  htmlFor="role"
                  style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}
                >
                  Role *
                </label>
                <select id="role" name="role" className="select" defaultValue="caller" required>
                  <option value="caller">caller</option>
                  <option value="admin">admin</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
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
                  {isPending ? 'Saving...' : 'Add User'}
                </button>
              </div>
            </form>
          </div>
        </>
      )}

      {/* Reset Password Modal */}
      {resetTargetUser && (
        <>
          <div
            className="drawer-backdrop active"
            onClick={() => setResetTargetUser(null)}
            style={{ zIndex: 110 }}
          />
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
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px',
              }}
            >
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>
                Reset Password for {resetTargetUser.display_name || resetTargetUser.email}
              </h2>
              <button
                type="button"
                onClick={() => setResetTargetUser(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {resetError && (
              <div
                className="form-error"
                style={{
                  padding: '8px 12px',
                  background: 'var(--color-danger-bg)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '12px',
                }}
              >
                ⚠️ {resetError}
              </div>
            )}

            <form onSubmit={handleResetSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label
                  htmlFor="reset_password"
                  style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginBottom: '4px' }}
                >
                  New Password * (min 8 characters)
                </label>
                <input
                  type="password"
                  id="reset_password"
                  name="password"
                  className="input"
                  required
                  minLength={8}
                  placeholder="••••••••"
                  autoFocus
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => setResetTargetUser(null)}
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
                  {isPending ? 'Updating...' : 'Reset Password'}
                </button>
              </div>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
