# ACTION-003 — Replace the Status filter with a Last Outcome filter

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The call sheet table shows a **LAST OUTCOME** column (`leads.last_disposition`)
— No answer, Shared info, Registered, Callback, Busy and so on. That is the
column the telecaller actually works from, and there is **no way to filter it**.

Meanwhile the filter bar has an "All Statuses" dropdown that filters
`leads.status`, a field that **is not displayed anywhere in the table**. So the
one filter that exists acts on an invisible field, and the visible field has no
filter at all. Bhratti cannot ask "show me everyone who did not answer" or
"show me my callbacks", which is the most common thing she needs.

Decision from Anirban: **replace** the Status dropdown with a Last Outcome
dropdown. The status filter is dropped, not kept alongside.

This is a **client-side filter only**. The leads are already loaded; do not
change any SQL.

## Three things that will silently break this task

**1. Saved presets already exist in browser localStorage.** They were stored
with the old shape `{ ..., status: 'hot', ... }` under key `tc_saved_filters`.
After the rename, applying an old preset yields `filters.lastOutcome ===
undefined`. That must **not** crash and must behave as "no outcome filter":

- the filter test must be falsy-safe, e.g. `if (filters.lastOutcome && ...)`
- the `<select>` must use `value={filters.lastOutcome || ''}` so React does not
  flip between controlled and uncontrolled and log a warning.

Do not write a localStorage migration. Degrading quietly to "no filter" is the
required behaviour.

**2. The database contains outcomes that are not in `DISPOSITION_META`.** Real
values live in `leads.last_disposition` that the telecaller app never defined,
written by the scraper/outreach side: `gate_physical`, `gate_accountmgmt`,
`gate_techops`, `gate_producteng`, `not_on_whatsapp`, `wa_freq_capped`. A label
lookup of `DISPOSITION_META[value].label` on these is `undefined` and will
render an empty option. The lookup **must fall back to the raw value**, e.g.
`DISPOSITION_META[v]?.label ?? v`. Build the dropdown from the outcomes actually
present in the loaded leads, exactly the way `cities` and `roleGroups` already
are — do not hardcode the list from `DISPOSITIONS`.

**3. "Not called yet" needs a sentinel, and `''` is already taken.** `''` means
"All Outcomes". Use the literal `__none__` for the "Not called yet" choice, and
have it match leads whose `last_disposition` is null or empty. It must not be
confused with a real outcome.

## Step 1 — report only, no changes

Read and report, changing nothing:

1. The current `FilterState` type in `telecaller-app/lib/savedFilters.ts`.
2. Every line in `telecaller-app/components/CallSheet.tsx` that mentions
   `status` or `statuses` (with line numbers).
3. Every line in `telecaller-app/components/FilterBar.tsx` that mentions
   `status` or `statuses` (with line numbers).
4. Confirm whether `DISPOSITION_META` is exported from
   `telecaller-app/lib/dispositions.ts` and what its value shape is.

Then state in one line the sentinel you will use for "Not called yet".

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** these three files:

- `telecaller-app/lib/savedFilters.ts`
- `telecaller-app/components/CallSheet.tsx`
- `telecaller-app/components/FilterBar.tsx`

Requirements:

- In `FilterState`, rename the `status: string` field to `lastOutcome: string`.
- In `CallSheet.tsx`:
  - initial filter state uses `lastOutcome: ''`;
  - replace the derived `statuses` list with an `outcomes` list built from the
    distinct non-empty `lead.last_disposition` values of the loaded leads, sorted;
  - replace the status filter test with: if `filters.lastOutcome` is `__none__`,
    keep only leads with no `last_disposition` (null or empty string); otherwise
    if `filters.lastOutcome` is truthy, keep only leads whose `last_disposition`
    equals it;
  - pass the new `outcomes` list to `FilterBar` instead of `statuses`.
- In `FilterBar.tsx`:
  - the prop `statuses: string[]` becomes `outcomes: string[]`;
  - the dropdown is bound to `filters.lastOutcome || ''` and its options are, in
    order: `All Outcomes` (value `''`), `Not called yet` (value `__none__`), then
    one option per entry in `outcomes`, whose **label** is
    `DISPOSITION_META[value]?.label ?? value` and whose **value** is the raw value;
  - `handleClearAll` resets `lastOutcome: ''` (not `status`).
- Keep the dropdown in the same position in the bar, with the same `.input`
  class and sizing. No other visual change.
- Non-goals: do not change `lib/queries.ts` or any SQL; do not touch the
  `invalid_number` server-side filter added in ACTION-001; do not add a second
  dropdown; do not write a localStorage migration; no schema or database change.

Then run these in `/root/projects/lead-manger/telecaller-app` and paste the real
output of each with its exit code. Not a summary. Installing dependencies in the
repo clone is expected and allowed for this check.

```
npm ci
```

```
npx tsc --noEmit
```

```
grep -rn "filters\.status" ../telecaller-app/components ../telecaller-app/lib
```

The grep must find nothing (exit code 1). If it finds a line, a rename was
missed.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Create a branch `feat/last-outcome-filter` off `main`.
- Commit the three changed files with a message saying what changed and why the
  filter moved from `status` to `last_disposition`.
- Push with `git push -u origin feat/last-outcome-filter`.
- Report the branch name, the commit hash, and the output of
  `git diff --name-only main..feat/last-outcome-filter`.

Do **not** commit to `main`, do **not** merge, and do **not** deploy. Claude
reviews, merges and deploys separately.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not touch `/opt/telecaller-app`. Do not run any `docker` command. Do not
  restart or rebuild anything.
- Do not connect to the database. No `psql`, no writes.
- Do not edit any file other than the three named above. `node_modules/` created
  by `npm ci` is expected and must not be committed (it is already gitignored).
- Do not touch `.env` or any credential file, and never print a secret value.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when, with pasted output:

1. `npx tsc --noEmit` exits `0` with no errors.
2. `grep -rn "filters\.status" telecaller-app/components telecaller-app/lib`
   finds nothing and exits `1`.
3. `git diff --name-only main..feat/last-outcome-filter` prints exactly these
   three paths and nothing else:
   ```
   telecaller-app/components/CallSheet.tsx
   telecaller-app/components/FilterBar.tsx
   telecaller-app/lib/savedFilters.ts
   ```
4. The branch `feat/last-outcome-filter` is pushed to `origin`.
