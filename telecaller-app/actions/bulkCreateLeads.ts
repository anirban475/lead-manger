'use server';

import { revalidatePath } from 'next/cache';
import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { normalizePhones } from '@/lib/phone';
import { getExistingContactIndex } from './getExistingContactIndex';
import crypto from 'crypto';

type BulkLeadInput = {
  company_name: string;
  contact_phone: string;
  contact_email?: string | null;
  contact_name?: string | null;
  contact_title?: string | null;
  city?: string | null;
};

type BulkImportResult = {
  inserted: number;
  skippedDuplicates: number;
  failed: { index: number; reason: string }[];
};

export async function bulkCreateLeads(leads: BulkLeadInput[]): Promise<BulkImportResult> {
  const session = await getSession();
  if (!session) {
    throw new Error('Unauthorized');
  }

  const result: BulkImportResult = {
    inserted: 0,
    skippedDuplicates: 0,
    failed: []
  };

  if (!leads || leads.length === 0) {
    return result;
  }

  // 1. Fetch fresh DB contact index for authoritative deduplication
  let existingIndex;
  try {
    existingIndex = await getExistingContactIndex();
  } catch (err) {
    console.error('Failed to retrieve contact index:', err);
    throw new Error('Failed to run deduplication check.');
  }

  const dbPhones = new Set(existingIndex.phones);
  const dbCompanies = new Set(existingIndex.companies);

  // Keep track of normalized entities inserted/processed in *this batch* to prevent self-duplication
  const batchPhones = new Set<string>();
  const batchCompanies = new Set<string>();

  const survivors: (BulkLeadInput & { company_key: string })[] = [];

  // 2. Validate and deduplicate
  for (let i = 0; i < leads.length; i++) {
    const lead = leads[i];
    const compName = (lead.company_name || '').trim();
    const phoneStr = (lead.contact_phone || '').trim();

    // Verification 1: Server-side validation
    if (!compName) {
      result.failed.push({ index: i, reason: 'Company Name is blank' });
      continue;
    }
    if (!phoneStr) {
      result.failed.push({ index: i, reason: 'Phone Number is blank' });
      continue;
    }

    const normalizedPhones = normalizePhones(phoneStr);
    if (normalizedPhones.length === 0) {
      result.failed.push({ index: i, reason: 'No valid phone numbers found' });
      continue;
    }

    const normalizedCompLower = compName.toLowerCase().trim();

    // Verification 2: Check database duplicates
    let isDupe = false;
    if (dbCompanies.has(normalizedCompLower)) {
      isDupe = true;
    }
    for (const phone of normalizedPhones) {
      if (dbPhones.has(phone.e164)) {
        isDupe = true;
        break;
      }
    }

    // Verification 3: Check batch duplicates (in-file self-duplication)
    if (batchCompanies.has(normalizedCompLower)) {
      isDupe = true;
    }
    for (const phone of normalizedPhones) {
      if (batchPhones.has(phone.e164)) {
        isDupe = true;
        break;
      }
    }

    if (isDupe) {
      result.skippedDuplicates++;
      continue;
    }

    // Record in batch registry
    batchCompanies.add(normalizedCompLower);
    for (const phone of normalizedPhones) {
      batchPhones.add(phone.e164);
    }

    survivors.push({
      ...lead,
      company_name: compName,
      contact_phone: phoneStr,
      company_key: 'csv_' + crypto.randomUUID()
    });
  }

  // 3. Execute batch inserts in a single transaction
  if (survivors.length === 0) {
    return result;
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    for (const lead of survivors) {
      await client.query(
        `INSERT INTO leads (
          company_key, company_name, contact_phone, contact_email, 
          contact_name, contact_title, contact_source, city, 
          status, origin, brand
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
        [
          lead.company_key,
          lead.company_name,
          lead.contact_phone,
          lead.contact_email || null,
          lead.contact_name || null,
          lead.contact_title || null,
          'csv',
          lead.city || null,
          'new',
          'csv',
          'jobdrive'
        ]
      );
      result.inserted++;
    }

    await client.query('COMMIT');
    
    revalidatePath('/queue');
    revalidatePath('/followups');
  } catch (err: any) {
    await client.query('ROLLBACK');
    console.error('Failed transaction in bulk import:', err);
    throw new Error(err.message || 'Database error occurred during transaction');
  } finally {
    client.release();
  }

  return result;
}
