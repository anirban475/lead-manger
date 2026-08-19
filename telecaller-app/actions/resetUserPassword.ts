'use server';

import { revalidatePath } from 'next/cache';
import bcrypt from 'bcryptjs';
import { pool } from '@/lib/db';
import { requireAdmin } from '@/lib/auth';

type ResetPasswordInput =
  | FormData
  | {
      userId?: number | string;
      id?: number | string;
      password?: string;
      newPassword?: string;
    };

export async function resetUserPassword(
  userIdOrInput: number | string | ResetPasswordInput,
  maybePassword?: string,
): Promise<{ success: boolean; error?: string }> {
  await requireAdmin();

  let userId: number;
  let newPassword = '';

  if (typeof userIdOrInput === 'number') {
    userId = userIdOrInput;
    newPassword = String(maybePassword || '');
  } else if (typeof userIdOrInput === 'string' && maybePassword !== undefined) {
    userId = parseInt(userIdOrInput, 10);
    newPassword = String(maybePassword || '');
  } else if (userIdOrInput instanceof FormData) {
    userId = parseInt(String(userIdOrInput.get('userId') || userIdOrInput.get('id') || ''), 10);
    newPassword = String(userIdOrInput.get('password') || userIdOrInput.get('newPassword') || '');
  } else if (typeof userIdOrInput === 'object' && userIdOrInput !== null) {
    userId = parseInt(String(userIdOrInput.userId ?? userIdOrInput.id ?? ''), 10);
    newPassword = String(userIdOrInput.newPassword ?? userIdOrInput.password ?? '');
  } else {
    return { success: false, error: 'Invalid input.' };
  }

  if (isNaN(userId)) {
    return { success: false, error: 'Invalid user ID.' };
  }

  if (!newPassword || newPassword.length < 8) {
    return { success: false, error: 'Password must be at least 8 characters.' };
  }

  const passwordHash = bcrypt.hashSync(newPassword, 10);

  try {
    await pool.query(
      'UPDATE app_users SET password_hash = $1 WHERE id = $2',
      [passwordHash, userId],
    );

    revalidatePath('/users');
    return { success: true };
  } catch (err: any) {
    console.error('Failed to reset user password');
    return { success: false, error: 'Database error occurred' };
  }
}
