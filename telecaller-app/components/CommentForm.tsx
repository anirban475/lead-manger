'use client';

import { useFormStatus } from 'react-dom';
import { useRef } from 'react';
import { addComment } from '@/actions/addComment';

function SubmitBtn() {
  const { pending } = useFormStatus();
  return (
    <button className="btn primary block" type="submit" disabled={pending}>
      {pending ? 'Adding…' : 'Add comment'}
    </button>
  );
}

export default function CommentForm({ companyKey }: { companyKey: string }) {
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = async (formData: FormData) => {
    try {
      await addComment(formData);
      formRef.current?.reset();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Error adding comment');
    }
  };

  return (
    <form ref={formRef} action={handleSubmit} className="stack">
      <input type="hidden" name="company_key" value={companyKey} />
      <div className="field" style={{ marginBottom: 8 }}>
        <textarea
          className="textarea"
          id="body"
          name="body"
          required
          placeholder="Add a freeform note or update for this lead..."
          style={{ minHeight: 60 }}
        />
      </div>
      <SubmitBtn />
    </form>
  );
}
