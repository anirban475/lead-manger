'use server';

import { revalidatePath } from 'next/cache';
import bcrypt from 'bcryptjs';
import { pool } from '@/lib/db';
import { requireAdmin } from '@/lib/auth';

type CreateUserInput =
  | FormData
  | {
      email?: string;
      display_name?: string;
      displayName?: string;
      password?: string;
      role?: string;
    };

export async function createUser(input: CreateUserInput): Promise<{ success: boolean; error?: string }> {
  await requireAdmin();

  let email = '';
  let displayName = '';
  let password = '';
  let role = '';

  if (input instanceof FormData) {
    email = String(input.get('email') || '');
    displayName = String(input.get('display_name') || input.get('displayName') || '');
    password = String(input.get('password') || '');
    role = String(input.get('role') || '');
  } else if (input && typeof input === 'object') {
    email = String(input.email || '');
    displayName = String(input.display_name || input.displayName || '');
    password = String(input.password || '');
    role = String(input.role || '');
  }

  email = email.trim().toLowerCase();
  displayName = displayName.trim();

  if (!email || !email.includes('@')) {
    return { success: false, error: 'A valid email address is required.' };
  }
  if (!displayName) {
    return { success: false, error: 'Display name is required.' };
  }
  if (!password || password.length < 8) {
    return { success: false, error: 'Password must be at least 8 characters.' };
  }
  if (role !== 'caller' && role !== 'admin') {
    return { success: false, error: 'Role must be either "caller" or "admin".' };
  }

  const passwordHash = bcrypt.hashSync(password, 10);

  try {
    await pool.query(
      `INSERT INTO app_users (email, password_hash, display_name, role, is_active)
       VALUES ($1, $2, $3, $4, true)`,
      [email, passwordHash, displayName, role],
    );

    revalidatePath('/users');
    return { success: true };
  } catch (err: any) {
    if (err?.code === '23505') {
      return { success: false, error: 'That email already has an account.' };
    }
    console.error('Failed to create user:', err);
    return { success: false, error: err?.message || 'Database error occurred' };
  }
}
