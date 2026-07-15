'use client';

import { useActionState } from 'react';
import { login } from '@/actions/auth';

export default function LoginForm() {
  const [error, formAction, pending] = useActionState(login, undefined);
  return (
    <form action={formAction}>
      {error ? <div className="form-error">{error}</div> : null}
      <div className="field">
        <label htmlFor="email">Email</label>
        <input className="input" id="email" name="email" type="email" autoComplete="username" required />
      </div>
      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          className="input"
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
      </div>
      <button className="btn primary block" type="submit" disabled={pending}>
        {pending ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
}
