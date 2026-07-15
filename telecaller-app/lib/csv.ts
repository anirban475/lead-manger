import { normalizePhones } from './phone';

export type TargetField = {
  key: string;
  label: string;
  required: boolean;
  autoGuesses: string[];
};

export const TARGET_FIELDS: TargetField[] = [
  { key: 'company_name', label: 'Company Name', required: true, autoGuesses: ['company', 'company name', 'name', 'firm', 'organization', 'organisation', 'employer', 'company_name'] },
  { key: 'contact_phone', label: 'Phone Number(s)', required: true, autoGuesses: ['phone', 'mobile', 'contact', 'contact phone', 'contact number', 'phone number', 'cell', 'telephone', 'contact_phone'] },
  { key: 'contact_email', label: 'Email Address', required: false, autoGuesses: ['email', 'email address', 'mail', 'contact_email'] },
  { key: 'contact_name', label: 'Contact Person', required: false, autoGuesses: ['person', 'contact person', 'contact name', 'hr name', 'hr', 'spoc', 'contact_name'] },
  { key: 'contact_title', label: 'Designation / Title', required: false, autoGuesses: ['title', 'designation', 'role', 'job title', 'contact title', 'contact_title'] },
  { key: 'city', label: 'City', required: false, autoGuesses: ['city', 'location', 'town', 'city'] }
];

export function guessMapping(headers: string[]): Record<string, string> {
  const mapping: Record<string, string> = {};
  for (const field of TARGET_FIELDS) {
    const matched = headers.find((h) => {
      const normalized = h.toLowerCase().trim();
      return field.autoGuesses.includes(normalized) || field.autoGuesses.some(g => normalized.includes(g) || g.includes(normalized));
    });
    mapping[field.key] = matched || '';
  }
  return mapping;
}

export type RowValidation = {
  valid: boolean;
  reason?: string;
};

export function validateRow(row: Record<string, string>): RowValidation {
  const comp = (row.company_name || '').trim();
  if (!comp) {
    return { valid: false, reason: 'Company Name is blank' };
  }
  const phone = (row.contact_phone || '').trim();
  if (!phone) {
    return { valid: false, reason: 'Phone Number is blank' };
  }
  const cleaned = normalizePhones(phone);
  if (cleaned.length === 0) {
    return { valid: false, reason: 'No valid phone numbers found' };
  }
  return { valid: true };
}
