# ACTION-011 — Show the job description in the lead detail views

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## ⚠️ A parallel run is active in this same working copy

Another session is working on `ACTION-010` (newspaper role extraction) in
`/root/projects/lead-manger` right now. That is a **single shared checkout**, so
this task must be written to coexist with it. The rules in "Coexistence" below
are not optional and matter more than speed.

This task touches **only `telecaller-app/`**. `ACTION-010` touches only
`jd-lead-newspaper/`. There is no file overlap — the only real risk is git
operations that sweep up someone else's work.

## Why this exists

`leads.job_description` is a new text column, populated by the newspaper radar.
**238 of 1140 leads have it, 179 of them are in the telecaller's live queue.**
It holds the actual advertised job text — what the employer is hiring for, and
often the role titles and the contact line.

The telecaller cannot see any of it. She opens a lead knowing the company, the
city and the applicant count, but not what the job actually is, so she has to
open the ad elsewhere or improvise on the call. Putting the text in front of her
is the whole point of the column.

## What the data actually looks like (measured, not assumed)

- Plain text. **No HTML** (`job_description ~ '<[a-zA-Z]'` is false today).
- Contains real newline characters.
- Average 745 characters, **maximum 9,615**. It can be very long.
- Newspaper OCR text is hard-wrapped mid-sentence at the original column width,
  so line breaks are sometimes awkward. Preserve them anyway — see trap 3.
- Only ~38% of queue leads have it, so the UI must cope with it being absent.

## Four traps

**1. Render it as TEXT, never as HTML.** This is scraped third-party content.
Do **not** use `dangerouslySetInnerHTML`, ever, even though today's sample has
no tags. Rendering scraped text as HTML is a stored-XSS vector: one ad
containing `<img onerror=...>` would execute in the telecaller's session. Put
the string in as a normal JSX child.

**2. The column must be added in two places or it fails silently.** Add
`job_description` to **both** the `Lead` type and the `LEAD_COLS` select list in
`telecaller-app/lib/queries.ts`. If you add it to the type only, TypeScript is
happy, the value is `undefined` at runtime, and the section simply never renders
with no error anywhere. Both, or the feature does nothing.

**3. Preserve the line breaks.** Use `whiteSpace: 'pre-wrap'`. Also set
`overflowWrap: 'anywhere'` so a long unbroken OCR token cannot push the drawer
sideways. Do not "tidy" the text by stripping newlines — for Naukri-sourced
descriptions those breaks are the bullet structure.

**4. Absent must mean hidden, not empty.** Some rows may hold an empty string
rather than NULL. Treat `null`, `undefined` and whitespace-only as absent and
render **nothing at all** — no heading, no empty card. 62% of queue leads would
otherwise show a blank section.

## Step 1 — report only, no changes

Read and report:

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD` and
   `git -C /root/projects/lead-manger status -s` (report it, do not clean it).
2. The current `LEAD_COLS` constant and the tail of the `Lead` type in
   `telecaller-app/lib/queries.ts`.
3. The section comments in `telecaller-app/components/LeadPanel.tsx` (the
   `{/* Section N: ... */}` lines) with line numbers.
4. The `className="card pad"` blocks in
   `telecaller-app/app/(app)/leads/[company_key]/page.tsx` with line numbers, and
   the `section-title` text of each.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** these three files:

**`telecaller-app/lib/queries.ts`**
- Add `job_description: string | null;` to the `Lead` type.
- Add `job_description` to `LEAD_COLS`. No cast needed, it is already `text`.

**`telecaller-app/components/LeadPanel.tsx`**
- Add a new section titled **Job Description**, placed immediately after
  Section 1 (Quick Contacts) and before Section 2 (Log Call Outcome), following
  the existing section markup (`drawer-section card pad`, an `<h3>` at
  `fontSize:'15px', fontWeight:700`).
- Render only when the description is present per trap 4.
- Body style: `whiteSpace:'pre-wrap'`, `overflowWrap:'anywhere'`,
  `fontSize:'13px'`, `lineHeight:1.5`, `color:'var(--text-body)'`.
- **Long text is collapsed by default.** If the trimmed description is longer
  than 400 characters, show only the first 400 characters followed by `…` plus a
  **Show more** / **Show less** toggle button (`.btn ghost`, small padding,
  `fontSize:'12px'`). Under 400 characters, render it in full with no toggle.
  Use a `useState` boolean; do not measure element heights.
- The toggle must reset to collapsed when a different lead is opened in the
  panel, so state does not leak between leads.

**`telecaller-app/app/(app)/leads/[company_key]/page.tsx`**
- Add a `<div className="card pad">` with `<div className="section-title">Job
  Description</div>` and the same `pre-wrap` body, placed **before** the
  Comments card. This is a server component: render the full text with no
  toggle, no client state.
- Same absent-means-hidden rule.

Non-goals: no schema change (the column already exists and
`deploy/schema.sql` already records it), no query/filter changes, no changes to
`CallSheet.tsx` or the queue table, no new columns in the list view.

Then run from `/root/projects/lead-manger/telecaller-app` and paste the real
output of each with its exit code:

```
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```
(not `npx tsc` — in this clone that resolves to an unrelated `tsc@2.0.4`)

```
grep -n "job_description" lib/queries.ts components/LeadPanel.tsx "app/(app)/leads/[company_key]/page.tsx"
```

```
grep -rn "dangerouslySetInnerHTML" components/LeadPanel.tsx "app/(app)/leads/[company_key]/page.tsx"
```
The last grep must find **nothing** (exit 1).

## Step 3 — commit directly to `main`

There is no feature branch for this task, deliberately: creating one would
switch the branch of the shared checkout and the parallel `ACTION-010` run would
commit onto it. Claude reviews the working-tree diff before you commit.

Wait for Claude's approval, then:

```
cd /root/projects/lead-manger
git add telecaller-app/lib/queries.ts telecaller-app/components/LeadPanel.tsx "telecaller-app/app/(app)/leads/[company_key]/page.tsx"
git commit -m "<message>"
git push origin main
```

Report the commit hash and `git show --stat HEAD`. The stat must list exactly
those three files.

If the push is rejected because `main` moved (the other run pushing), do
`git pull --rebase origin main` and push again. Do not force-push.

## Coexistence — hard rules

- **Stay on `main`.** Do not run `git checkout -b`, `git switch -c`, or check
  out any other branch. The other run needs this checkout on `main`.
- **Stage only the three named files, by explicit path.** Never `git add -A`,
  `git add .`, `git add -u`, or `git commit -a`. The other run has work in
  progress in this tree and those commands would sweep it into your commit.
- **Never** `git stash`, `git checkout .`, `git restore`, `git reset --hard`, or
  `git clean`. If the tree is dirty with `jd-lead-newspaper/` changes, that is
  the other run's work — leave it exactly as it is and carry on. Your edits are
  independent of it.
- If `git pull --ff-only` fails because the tree is dirty, **do not clean it**.
  Report it and continue; you do not need a pull to edit these three files.
- Do not touch `jd-lead-newspaper/`, `actions/ACTION-010-*`, or anything outside
  `telecaller-app/`.
- Do not run `docker`. Do not connect to the database. No deploy in this task.
- One step per reply. Finish a step, report, and wait.

## Acceptance

1. `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` exits `0`.
2. `job_description` appears in `lib/queries.ts` **twice** (type and `LEAD_COLS`)
   and in both view files.
3. `grep -rn "dangerouslySetInnerHTML"` on the two view files finds nothing.
4. `git show --stat HEAD` lists exactly the three files, and `git status -s`
   still shows any pre-existing `jd-lead-newspaper/` changes untouched.
