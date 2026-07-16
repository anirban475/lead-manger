'use server';

import { revalidatePath } from 'next/cache';
import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { normalizePhones } from '@/lib/phone';
import crypto from 'crypto';

export async function createLead(formData: FormData): Promise<{ success: boolean; error?: string }> {
  const session = await getSession();
  if (!session) {
    throw new Error('Unauthorized');
  }

  const companyName = String(formData.get('company_name') || '').trim();
  const contactPhone = String(formData.get('contact_phone') || '').trim();
  const contactEmail = String(formData.get('contact_email') || '').trim() || null;
  const contactName = String(formData.get('contact_name') || '').trim() || null;
  const contactTitle = String(formData.get('contact_title') || '').trim() || null;
  const city = String(formData.get('city') || '').trim() || null;

  if (!companyName) {
    return { success: false, error: 'Company name is required' };
  }

  const phones = normalizePhones(contactPhone);
  if (phones.length === 0) {
    return { success: false, error: 'At least one valid phone number is required' };
  }

  // Generate unique manual company key
  const companyKey = 'manual_' + crypto.randomUUID();

  try {
    await pool.query(
      `INSERT INTO leads (
        company_key, company_name, contact_phone, contact_email, 
        contact_name, contact_title, contact_source, city, 
        status, origin, brand
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
      [
        companyKey,
        companyName,
        contactPhone,
        contactEmail,
        contactName,
        contactTitle,
        'manual',
        city,
        'new',
        'manual',
        'jobdrive',
      ]
    );

    revalidatePath('/queue');
    revalidatePath('/followups');
    return { success: true };
  } catch (err: any) {
    console.error('Failed to create lead:', err);
    return { success: false, error: err.message || 'Database error occurred' };
  }
}
