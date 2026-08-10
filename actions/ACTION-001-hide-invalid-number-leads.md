# ACTION-001 — Hide invalid-number leads from the telecaller queue

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

When a telecaller dials a lead and the number is dead, she logs the outcome
**Invalid number**. That lead then keeps sitting in the queue, sorted by score
like any other, so it comes back around and gets dialled again. There are
**31 such leads in the live database right now**, several of them high-score
rows near the top of the list (Canton Laboratories, Dot Graphics Llp, Aswani
Industries, Sundyota Numandis Pharmaceuticals). Every one of them is a phone
number already proven dead, and there is nothing in the app that removes them.
The caller pays for this in wasted dials every day.

The fix is to stop returning them from the two list queries that feed the
Queue and Follow-ups screens.

## Two things that will silently break this task

Read both before writing any code. Each one produces a change that looks
correct, passes a build, and does nothing (or does damage).

**1. This is NOT `status`.** The screen column reads "Invalid number", but that
is `leads.last_disposition`, not `leads.status`. In `lib/dispositions.ts` the
map is `STATUS_MAP.invalid_number = 'handed_off'`, and the database constraint
`leads_status_chk` does not even permit the string `'invalid_number'` as a
status value. A filter written against `status` matches zero rows and ships a
no-op. The column to filter is **`last_disposition`**.

**2. A plain `<>` comparison will empty the queue.** In SQL,
`NULL <> 'invalid_number'` evaluates to NULL, not TRUE, so a `WHERE
last_disposition <> 'invalid_number'` clause silently discards every row where
`last_disposition IS NULL`. That is **more than 250 leads** in the live
database — every lead that has never been called, which is most of the queue.
The predicate must be NULL-safe. Use:

```sql
last_disposition IS DISTINCT FROM 'invalid_number'
```

## Step 1 — report only, no changes

Read and report, changing nothing:

1. The full `WHERE` clause of `getQueue` in `telecaller-app/lib/queries.ts`.
2. The full `WHERE` clause of `getFollowups` in the same file.
3. The value of the `CLOSED` constant in that file, and whether
   `'invalid_number'` appears anywhere in it.
4. What `STATUS_MAP.invalid_number` maps to in
   `telecaller-app/lib/dispositions.ts`.

Then state, in one line, which column you are going to filter on and which
operator you are going to use.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** `telecaller-app/lib/queries.ts`.

Requirements:

- Add a single shared constant next to the existing `HAS_PHONE` constant, named
  `NOT_INVALID_NUMBER`, whose value is the SQL fragment
  `last_disposition IS DISTINCT FROM 'invalid_number'`. Give it a one-line
  comment saying why it exists (a dead number must not be re-dialled).
- Add that constant to the `WHERE` conditions of **both** `getQueue` **and**
  `getFollowups`. Both, not one.
- Do not change `getLead`. Opening a lead by direct URL must still work, the
  same way the phone-gate already behaves.
- Do not change `getDispositionCounts`, `getLeadCalls`, or the
  `query_conversion` view. Invalid-number calls must stay in the Stats page and
  in the historical record. This task hides leads from two lists, it does not
  delete or unlog anything.
- Non-goal: no UI/component changes, no new filter checkbox, no schema change,
  no database writes of any kind.

Then run both of these, in `/root/projects/lead-manger`, and paste the real
output of each with its exit code. Not a summary of the output.

```
grep -n "IS DISTINCT FROM 'invalid_number'" telecaller-app/lib/queries.ts
```

```
sed -n '/const CLOSED/,/^}/p' telecaller-app/lib/queries.ts | head -40
```

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Create a branch `fix/hide-invalid-number-leads` off `main`.
- Commit `telecaller-app/lib/queries.ts` to that branch with a message saying
  what it does and why it filters `last_disposition` rather than `status`.
- Push with `git push -u origin fix/hide-invalid-number-leads`.
- Report the branch name and the commit hash.

Do **not** commit to `main` and do **not** merge. Claude reviews the branch and
merges it after verification.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not touch `/opt/telecaller-app`. That is the running production app and it
  is not yours to edit or deploy in this task.
- Do not run any `docker` command. Do not restart, stop or rebuild the
  `telecaller-app` container or `shared-postgres`.
- Do not connect to the database. No `psql`, no writes, no migrations. This task
  is a code change only.
- Do not edit any file other than `telecaller-app/lib/queries.ts`.
- Do not touch `.env` or any credential file, and never print a secret value.
- One step per reply. Finish a step, report, and wait for the next instruction.

## Acceptance

Done when:

1. `grep -c "IS DISTINCT FROM 'invalid_number'" telecaller-app/lib/queries.ts`
   prints `2` and exits `0`, and
2. that grep's two hits are inside `getQueue` and `getFollowups` respectively,
   and
3. `git diff --name-only main..fix/hide-invalid-number-leads` prints exactly
   `telecaller-app/lib/queries.ts` and nothing else, and
4. the branch `fix/hide-invalid-number-leads` is pushed to `origin`.
