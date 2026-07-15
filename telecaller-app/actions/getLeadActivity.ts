'use server';

import { getLeadActivity, TimelineItem } from '@/lib/queries';
import { getSession } from '@/lib/auth';

/**
 * Fetch chronological calls and comments activity for a company.
 * Auth-checked.
 */
export async function getLeadActivityAction(companyKey: string): Promise<TimelineItem[]> {
  const session = await getSession();
  if (!session) throw new Error('Unauthorized');

  return getLeadActivity(companyKey);
}
