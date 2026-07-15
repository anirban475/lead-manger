'use client';

import { useState } from 'react';
import { useFormStatus } from 'react-dom';
import { logCall } from '@/actions/logCall';
import { DISPOSITIONS, DISPOSITION_META, DISPOSITION_GROUPS, NEEDS_FOLLOWUP, type Disposition } from '@/lib/dispositions';
import { todayISO } from '@/lib/format';

function SubmitBtn({ disabled }: { disabled: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button className="btn primary block lg" type="submit" disabled={disabled || pending}>
      {pending ? 'Saving…' : 'Log call'}
    </button>
  );
}

export default function LogCallForm({ companyKey }: { companyKey: string }) {
  const [disp, setDisp] = useState<Disposition | ''>('');
  const showFollow = disp !== '' && NEEDS_FOLLOWUP.includes(disp);
  const today = todayISO();

  return (
    <form action={logCall} className="stack">
      <input type="hidden" name="company_key" value={companyKey} />
      <input type="hidden" name="channel" value="tel" />

      <div className="field">
        <label>Outcome</label>
        <div style={{ display: 'grid', gap: 12 }}>
          {DISPOSITION_GROUPS.map((g) => {
            const groupDisps = DISPOSITIONS.filter((d) => DISPOSITION_META[d].group === g.key);
            return (
              <div key={g.key}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '.02em', marginBottom: 6 }}>
                  {g.label}
                </div>
                <div className="disp-grid">
                  {groupDisps.map((d) => (
                    <label key={d} className="disp-opt">
                      <input type="radio" name="disposition" value={d} required onChange={() => setDisp(d)} />
                      <span>{DISPOSITION_META[d].label}</span>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {showFollow ? (
        <div className="field">
          <label htmlFor="follow_up_date">Follow-up date</label>
          <input
            className="input"
            id="follow_up_date"
            name="follow_up_date"
            type="date"
            defaultValue={today}
            min={today}
          />
        </div>
      ) : null}

      <div className="field">
        <label htmlFor="notes">Notes</label>
        <textarea
          className="textarea"
          id="notes"
          name="notes"
          placeholder="What happened on the call? HR capacity, pain, wrong-number detail…"
        />
      </div>

      <SubmitBtn disabled={disp === ''} />
    </form>
  );
}
