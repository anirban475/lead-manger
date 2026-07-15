'use server';

import { revalidatePath } from 'next/cache';
import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { normalizePhones } from '@/lib/phone';

export async function updateLeadContact(formData: FormData): Promise<{ success: boolean; error?: string }> {
  const session = await getSession();
  if (!session) {
    throw new Error('Unauthorized');
  }

  const companyKey = String(formData.get('company_key') || '').trim();
  const contactPhone = String(formData.get('contact_phone') || '').trim();
  const contactEmail = String(formData.get('contact_email') || '').trim() || null;
  const contactName = String(formData.get('contact_name') || '').trim() || null;
  const contactTitle = String(formData.get('contact_title') || '').trim() || null;

  if (!companyKey) {
    return { success: false, error: 'Company key is required' };
  }

  const phones = normalizePhones(contactPhone);
  if (phones.length === 0) {
    return { success: false, error: 'At least one valid phone number is required' };
  }

  try {
    const result = await pool.query(
      `UPDATE leads SET
        contact_phone = $1,
        contact_email = $2,
        contact_name = $3,
        contact_title = $4,
        contact_source = 'manual',
        updated_at = now()
      WHERE company_key = $5`,
      [contactPhone, contactEmail, contactName, contactTitle, companyKey]
    );

    if (result.rowCount === 0) {
      return { success: false, error: 'Lead not found' };
    }

    revalidatePath('/queue');
    revalidatePath('/followups');
    revalidatePath(`/leads/${encodeURIComponent(companyKey)}`);
    return { success: true };
  } catch (err: any) {
    console.error('Failed to update lead contact:', err);
    return { success: false, error: err.message || 'Database error occurred' };
  }
}
