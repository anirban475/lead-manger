'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';
import { pool } from '@/lib/db';
import { getSession } from '@/lib/auth';
import { STATUS_MAP, DISPOSITION_META, isDisposition } from '@/lib/dispositions';
import { normalizePhones } from '@/lib/phone';

/**
 * Log a call outcome in one transaction:
 *  - append an immutable telecall_logs row (attributed to the signed-in caller)
 *  - update the lead's status / next_action / denormalized latest-call fields
 *  - if opted_out: force status and suppress the normalized phone + email so the
 *    scraper never re-contacts them.
 */
export async function logCall(formData: FormData): Promise<void> {
  const session = await getSession();
  if (!session) throw new Error('Unauthorized');
  const caller = session.displayName || session.email;

  const companyKey = String(formData.get('company_key') || '');
  const disposition = String(formData.get('disposition') || '');
  if (!companyKey || !isDisposition(disposition)) throw new Error('Invalid input');

  const channel = String(formData.get('channel') || 'tel');
  const notes = formData.get('notes') ? String(formData.get('notes')).trim() || null : null;
  const followRaw = String(formData.get('follow_up_date') || '').trim();
  const followUp = /^\d{4}-\d{2}-\d{2}$/.test(followRaw) ? followRaw : null;

  const status = STATUS_MAP[disposition];
  const nextAction = DISPOSITION_META[disposition].label;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    await client.query(
      `INSERT INTO telecall_logs
         (company_key, caller, channel, disposition, reason, notes, follow_up_date)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [companyKey, caller, channel, disposition, null, notes, followUp],
    );

    await client.query(
      `UPDATE leads SET
         status = $2,
         next_action = $3,
         next_action_date = COALESCE($4::date, next_action_date),
         last_disposition = $5,
         last_called_at = now(),
         call_count = call_count + 1,
         updated_at = now()
       WHERE company_key = $1`,
      [companyKey, status, nextAction, followUp, disposition],
    );

    if (disposition === 'opted_out') {
      const res = await client.query(
        `SELECT contact_phone, contact_email FROM leads WHERE company_key = $1`,
        [companyKey],
      );
      const lead = res.rows[0] as { contact_phone: string | null; contact_email: string | null } | undefined;
      const contacts: string[] = [];
      const phs = normalizePhones(lead?.contact_phone);
      for (const ph of phs) {
        contacts.push(ph.e164);
      }
      const email = lead?.contact_email?.trim();
      if (email && email !== '-') contacts.push(email.toLowerCase());
      for (const c of contacts) {
        await client.query(
          `INSERT INTO suppression (contact, reason) VALUES ($1, $2) ON CONFLICT (contact) DO NOTHING`,
          [c, 'telecall_opt_out'],
        );
      }
    }

    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }

  revalidatePath('/queue');
  revalidatePath('/followups');
  revalidatePath(`/leads/${companyKey}`);

  const noRedirect = formData.get('no_redirect') === 'true';
  if (!noRedirect) {
    redirect(`/leads/${encodeURIComponent(companyKey)}`);
  }
}
