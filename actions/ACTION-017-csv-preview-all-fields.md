# ACTION-017 — Show all mapped fields in the CSV preview table

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## ⚠️ Coexistence — a parallel run may be active

The newspaper session works in this same checkout. All ACTION-011 rules apply:

- **Stay on `main`.** Never create or switch branches.
- **Never** `git add -A`, `git commit -a`, `git stash`, `git reset`,
  `git checkout .`, `git restore` or `git clean`. Stage only the one named file.
- If the tree is dirty with `jd-lead-newspaper/` changes, that is the other
  run's work — **leave it exactly as it is**.
- Do not touch `jd-lead-newspaper/` or `actions/ACTION-012*` / `ACTION-013*`.
- No docker, no deploy, no database connection in this task.

## Why this exists

ACTION-015 expanded the CSV import to eleven mappable fields, but the Step-3
preview table still shows only five of them: company name, phone, email, contact
person and city. Website, industry, job description, role titles and source are
mapped and imported but **invisible before import**, so the user cannot confirm
they mapped the right columns until after the rows are in the database.

Every mapped field must be visible in the preview.

## What the table shows now

Six columns: `Row Status`, `Company Name`, `Phone Number(s)`, `Email`,
`Contact Person`, `City`. Note `Contact Person` currently merges
`contact_name` and `contact_title` into one cell.

## What it must show

Twelve columns — the status column plus all eleven mapped fields, each in its
own column, in this order:

| # | Header | Field |
|---|---|---|
| 1 | Row Status | (status / actions) |
| 2 | Company Name | `company_name` |
| 3 | Phone Number(s) | `contact_phone` |
| 4 | Email | `contact_email` |
| 5 | Contact Person | `contact_name` |
| 6 | Designation / Title | `contact_title` |
| 7 | City | `city` |
| 8 | Company Website | `company_website` |
| 9 | Industry | `industry` |
| 10 | Job Description | `job_description` |
| 11 | Role Titles | `role_titles` |
| 12 | Source | `contact_source` |

`contact_title` gets its **own** column — stop merging it into Contact Person.

## Three traps

**1. `job_description` will destroy the table if rendered in full.** Measured on
live data: average 745 characters, **maximum 9,615**. One such row would make
the preview unusable. Truncate it to the **first 60 characters plus `…`** and
put the full text in the cell's `title` attribute so it is available on hover.
Do not truncate the other columns' data.

**2. Twelve columns will not fit the modal — that is fine, but only if the
scroll survives.** The table already sits inside `.table-responsive`, which has
`overflow-x: auto`. **Keep that wrapper and its `maxHeight`/`overflowY` inline
style exactly as they are.** Do not set a fixed table width, do not add
`tableLayout: 'fixed'`, and do not put `overflow: hidden` anywhere in the chain,
or the right-hand columns become unreachable. Also widen the modal for this step
only: change the `maxWidth` at line ~331 from `'860px'` to `'1200px'` for the
`validate` step, leaving the other steps at `'620px'`.

**3. Do not touch anything but presentation.** The inline-edit inputs for the
two mandatory fields on error rows (`company_name`, `contact_phone`) must keep
working exactly as they do now. Do not change `RowData` (all eleven fields are
already on it), `processRows`, `validateRow`, the dedup logic, the import
payload, or `handleImport`. This task renders existing data and nothing else.

## Step 1 — report only, no changes

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD` and
   `git status -s` (report, do not clean).
2. The `<thead>` block of the preview table in
   `telecaller-app/components/CsvUploadModal.tsx`, with line numbers.
3. The `<tbody>` row-rendering block, with line numbers — specifically how the
   Contact Person cell currently combines name and title, and how the
   inline-edit inputs for the error rows are rendered.
4. The `maxWidth` line for the modal container, with its line number.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** `telecaller-app/components/CsvUploadModal.tsx`.

- Replace the six `<th>` with the twelve above, same styling as the existing
  headers.
- Render the matching twelve `<td>` per row, in the same order.
- Empty or whitespace-only values render as `—`, matching the existing style
  (`{row.x || '—'}`).
- `job_description`: `{row.job_description ? row.job_description.slice(0, 60) + (row.job_description.length > 60 ? '…' : '') : '—'}` with
  `title={row.job_description || undefined}` on the `<td>`.
- Keep the inline-edit `<input>` behaviour for `company_name` and
  `contact_phone` on error rows exactly as it is.
- Change the modal `maxWidth` for the `validate` step to `'1200px'`.
- Change nothing else in the file.

Then run from `/root/projects/lead-manger/telecaller-app` and paste the real
output of each with its exit code:

```
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```
(not `npx tsc`)

```
grep -c "<th" components/CsvUploadModal.tsx
```

```
grep -n "table-responsive" components/CsvUploadModal.tsx
```
The wrapper must still be there.

State in your reply how many `<th>` the **preview** table has (the mapping table
in Step 2 of the wizard also has `<th>`, so give the preview count specifically).

## Step 3 — commit to `main`

Wait for Claude's approval, then stage **only**
`telecaller-app/components/CsvUploadModal.tsx` by explicit path, commit to
`main`, push. Report the hash and `git show --stat HEAD` — exactly one file. If
the push is rejected because `main` moved, `git pull --rebase origin main` and
push again. Never force-push.

## Acceptance

1. `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` exits `0`.
2. The preview table has **12** `<th>`, in the order listed above.
3. `.table-responsive` wrapper still present with its `overflow` intact.
4. `job_description` is truncated in the cell and full in `title`.
5. `git show --stat HEAD` lists exactly one file, and `git status -s` still
   shows any pre-existing `jd-lead-newspaper/` changes untouched.
