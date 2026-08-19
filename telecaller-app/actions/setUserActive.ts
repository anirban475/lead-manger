'use server';

import { revalidatePath } from 'next/cache';
import { pool } from '@/lib/db';
import { requireAdmin } from '@/lib/auth';

export async function setUserActive(
  userIdOrInput: number | { userId: number; isActive: boolean },
  maybeIsActive?: boolean,
): Promise<{ success: boolean; error?: string }> {
  const adminSession = await requireAdmin();

  let userId: number;
  let isActive: boolean;

  if (typeof userIdOrInput === 'number') {
    userId = userIdOrInput;
    isActive = Boolean(maybeIsActive);
  } else if (typeof userIdOrInput === 'object' && userIdOrInput !== null) {
    userId = userIdOrInput.userId;
    isActive = Boolean(userIdOrInput.isActive);
  } else {
    return { success: false, error: 'Invalid input.' };
  }

  if (isNaN(userId)) {
    return { success: false, error: 'Invalid user ID.' };
  }

  const userRes = await pool.query<{ email: string }>(
    'SELECT email FROM app_users WHERE id = $1',
    [userId],
  );
  const targetUser = userRes.rows[0];
  if (!targetUser) {
    return { success: false, error: 'User not found.' };
  }

  if (targetUser.email.toLowerCase().trim() === adminSession.email.toLowerCase().trim()) {
    return { success: false, error: 'You cannot deactivate your own account.' };
  }

  try {
    await pool.query(
      'UPDATE app_users SET is_active = $1 WHERE id = $2',
      [isActive, userId],
    );

    revalidatePath('/users');
    return { success: true };
  } catch (err: any) {
    console.error('Failed to update user active status:', err);
    return { success: false, error: 'Database error occurred' };
  }
}
