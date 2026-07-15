export const DISPOSITIONS = [
  // Couldn't connect
  'no_answer',
  'busy',
  'call_dropped',
  'invalid_number',
  // Talked
  'connected',
  'info_shared',
  'interested',
  'callback',
  'meeting_booked',
  'not_interested',
  'converted',
  'opted_out',
  'registered',
] as const;

export type Disposition = (typeof DISPOSITIONS)[number];

export type Tone = 'good' | 'bad' | 'warn' | 'neutral';
export type DispGroup = 'reach' | 'talk';

export const DISPOSITION_META: Record<Disposition, { label: string; tone: Tone; group: DispGroup }> = {
  // Couldn't connect
  no_answer: { label: 'No answer', tone: 'warn', group: 'reach' },
  busy: { label: 'Busy', tone: 'warn', group: 'reach' },
  call_dropped: { label: 'Call dropped', tone: 'warn', group: 'reach' },
  invalid_number: { label: 'Invalid number', tone: 'bad', group: 'reach' },
  // Talked
  connected: { label: 'Connected', tone: 'neutral', group: 'talk' },
  info_shared: { label: 'Shared info', tone: 'good', group: 'talk' },
  interested: { label: 'Interested', tone: 'good', group: 'talk' },
  callback: { label: 'Callback', tone: 'warn', group: 'talk' },
  meeting_booked: { label: 'Meeting booked', tone: 'good', group: 'talk' },
  not_interested: { label: 'Not interested', tone: 'bad', group: 'talk' },
  converted: { label: 'Converted', tone: 'good', group: 'talk' },
  opted_out: { label: 'Opted out', tone: 'bad', group: 'talk' },
  registered: { label: 'Registered', tone: 'good', group: 'talk' },
};

export const DISPOSITION_GROUPS: { key: DispGroup; label: string }[] = [
  { key: 'reach', label: "Couldn't connect" },
  { key: 'talk', label: 'Talked' },
];

// Disposition -> leads.status (keeps the scraper's existing status vocabulary intact).
export const STATUS_MAP: Record<Disposition, string> = {
  not_interested: 'lost',
  converted: 'won',
  opted_out: 'opted_out',
  info_shared: 'hot',
  interested: 'hot',
  callback: 'hot',
  meeting_booked: 'hot',
  connected: 'handed_off',
  no_answer: 'handed_off',
  busy: 'handed_off',
  call_dropped: 'handed_off',
  invalid_number: 'handed_off',
  registered: 'registered',
};

// Dispositions that imply a future retry — the UI offers a follow-up date for these.
export const NEEDS_FOLLOWUP: readonly Disposition[] = [
  'no_answer',
  'busy',
  'call_dropped',
  'callback',
  'interested',
  'info_shared',
  'meeting_booked',
];

export function isDisposition(v: string): v is Disposition {
  return (DISPOSITIONS as readonly string[]).includes(v);
}
