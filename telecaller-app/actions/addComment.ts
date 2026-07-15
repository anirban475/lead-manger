'use server';

import { revalidatePath } from 'next/cache';
import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';

/**
 * Inserts a freeform comment on a lead, attributed to the logged-in user.
 */
export async function addComment(formData: FormData): Promise<void> {
  const session = await getSession();
  if (!session) throw new Error('Unauthorized');
  const author = session.displayName || session.email;

  const companyKey = String(formData.get('company_key') || '');
  const body = String(formData.get('body') || '').trim();

  if (!companyKey || !body) throw new Error('Invalid input');

  await pool.query(
    `INSERT INTO lead_comments (company_key, author, body) VALUES ($1, $2, $3)`,
    [companyKey, author, body],
  );

  revalidatePath(`/leads/${encodeURIComponent(companyKey)}`);
}
