'use server';

import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { normalizePhones } from '@/lib/phone';

export async function getExistingContactIndex(): Promise<{ phones: string[]; companies: string[] }> {
  const session = await getSession();
  if (!session) {
    throw new Error('Unauthorized');
  }

  try {
    // Fetch all active company names and phone numbers
    const res = await pool.query(`SELECT contact_phone, company_name FROM leads`);
    
    const phones = new Set<string>();
    const companies = new Set<string>();

    for (const row of res.rows) {
      if (row.company_name) {
        companies.add(row.company_name.toLowerCase().trim());
      }
      if (row.contact_phone) {
        const normalized = normalizePhones(row.contact_phone);
        for (const p of normalized) {
          phones.add(p.e164);
        }
      }
    }

    return {
      phones: Array.from(phones),
      companies: Array.from(companies)
    };
  } catch (err) {
    console.error('Failed to get existing contact index:', err);
    throw err;
  }
}
