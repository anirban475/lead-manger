export type CleanPhone = {
  e164: string;
  tel: string;
  waMobile: string;
  waWeb: string;
  lowConfidence: boolean;
};

export type NormalizedPhone =
  | { valid: true; e164: string; tel: string; wa: string; lowConfidence: boolean }
  | { valid: false; reason: 'needs_enrichment' };

/**
 * Normalizes a single raw phone number.
 */
function normalizeSingle(part: string): CleanPhone | null {
  const trimmed = part.trim();
  const hasPlus = trimmed.startsWith('+');
  const digits = trimmed.replace(/[^0-9]/g, '');

  if (digits.length < 8) return null;

  let e164: string;
  let lowConfidence = false;

  if (hasPlus) {
    e164 = '+' + digits;
  } else if (digits.length === 10 && /^[6-9]/.test(digits)) {
    e164 = '+91' + digits;
  } else if (digits.length === 11 && digits.startsWith('0')) {
    e164 = '+91' + digits.slice(1);
  } else if (digits.length === 12 && digits.startsWith('91')) {
    e164 = '+' + digits;
  } else {
    e164 = '+' + digits;
    lowConfidence = true;
  }

  if (e164.length > 16) {
    lowConfidence = true;
  }

  const cleanDigits = e164.replace('+', '');
  return {
    e164,
    tel: `tel:${e164}`,
    waMobile: `https://wa.me/${cleanDigits}`,
    waWeb: `https://web.whatsapp.com/send?phone=${cleanDigits}`,
    lowConfidence,
  };
}

/**
 * Parses and normalizes a phone string containing one or more numbers.
 * Splits on common delimiters like /, ,, &, |, and the word 'or'.
 */
export function normalizePhones(raw: string | null | undefined): CleanPhone[] {
  if (raw == null) return [];
  const parts = raw.split(/[\/,|&]|\bor\b/i);
  const results: CleanPhone[] = [];
  for (const part of parts) {
    const clean = normalizeSingle(part);
    if (clean) results.push(clean);
  }
  return results;
}

/**
 * Backward-compatible wrapper returning the first valid number.
 */
export function normalizePhone(raw: string | null | undefined): NormalizedPhone {
  const list = normalizePhones(raw);
  if (list.length === 0) return { valid: false, reason: 'needs_enrichment' };
  const first = list[0];
  return {
    valid: true,
    e164: first.e164,
    tel: first.tel,
    wa: first.waMobile,
    lowConfidence: first.lowConfidence,
  };
}

