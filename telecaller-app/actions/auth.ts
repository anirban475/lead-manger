'use server';

import { redirect } from 'next/navigation';
import { verifyCredentials, createSession, destroySession } from '@/lib/auth';

export async function login(
  _prev: string | undefined,
  formData: FormData,
): Promise<string | undefined> {
  const email = String(formData.get('email') || '');
  const password = String(formData.get('password') || '');
  if (!email || !password) return 'Enter your email and password.';

  let session;
  try {
    session = await verifyCredentials(email, password);
  } catch {
    return 'Sign-in is temporarily unavailable. Try again.';
  }
  if (!session) return 'Invalid email or password.';

  await createSession(session);
  redirect('/queue'); // throws control-flow; nothing after runs
}

export async function logout(): Promise<void> {
  await destroySession();
  redirect('/login');
}
