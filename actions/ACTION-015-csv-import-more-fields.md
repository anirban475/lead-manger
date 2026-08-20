# ACTION-015 — Expand the CSV import field mapping

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## ⚠️ Coexistence — a parallel run may be active

The newspaper session works in this same checkout. All the ACTION-011 rules
still apply and are not optional:

- **Stay on `main`.** Never create or switch branches.
- **Never** `git add -A`, `git add .`, `git commit -a`, `git stash`, `git reset`,
  `git checkout .`, `git restore` or `git clean`. Stage only the three named
  files, by explicit path.
- If the tree is dirty with `jd-lead-newspaper/` changes, that is the other
  run's work — **leave it exactly as it is**.
- Do not touch `jd-lead-newspaper/` or any other `actions/ACTION-*` brief.
- No docker, no deploy, no database connection in this task.

## Why this exists

The bulk CSV import only lets the user map **six** fields: company name, phone,
email, contact person, title and city. Anything else in their spreadsheet —
website, industry, the job text, the roles, where the lead came from — is
silently dropped on import, and they then have to fill it in by hand or lose it.

Anirban has chosen the full set. **The mandatory fields do not change.**

## The field set (final, decided by Anirban)

**Mandatory — unchanged, still exactly these two:**

| Key | Label |
|---|---|
| `company_name` | Company Name |
| `contact_phone` | Phone Number(s) |

**Optional — the six existing minus the two above, plus five new:**

| Key | Label | Status |
|---|---|---|
| `contact_email` | Email Address | exists |
| `contact_name` | Contact Person | exists |
| `contact_title` | Designation / Title | exists |
| `city` | City | exists |
| `company_website` | Company Website | **new** |
| `industry` | Industry | **new** |
| `job_description` | Job Description | **new** |
| `role_titles` | Role Titles | **new** — `text[]`, see trap 1 |
| `contact_source` | Source | **new** — see trap 2 |

Eleven mappable fields in total. Do **not** make any of the new ones required.

The database grant has already been extended by Claude — `telecaller_app` can
now INSERT `company_website`, `industry`, `job_description` and `role_titles`.
Do not run any SQL.

## Four traps

**1. `role_titles` is a Postgres `text[]`, not text.** Passing the raw CSV
string would either error or store a malformed single-element array. Split the
cell on commas, `.trim()` each part, drop empty parts, and pass the resulting
**JavaScript array** as the parameter — node-postgres converts a JS array to a
Postgres array automatically. If nothing survives the split, pass **`null`**,
not `[]`, so an empty cell does not become an empty array.

**2. `contact_source` is currently hardcoded to `'csv'` in
`actions/bulkCreateLeads.ts`.** Now it is mappable, so: if the mapped cell has a
non-empty trimmed value, use it; otherwise fall back to **`'csv'`** exactly as
today. Never insert an empty string. **`source_query` must stay untouched and
NULL** — it is the scraper's learning signal and CSV leads are deliberately
excluded from `query_conversion`. Do not map it, do not set it.

**3. The INSERT column list must stay in sync with the mapping.** Adding a field
to `TARGET_FIELDS` without adding it to the `INSERT INTO leads (...)` column
list and its `$n` placeholder means the user maps the column, sees it in the
preview, imports "successfully", and the value is silently discarded. Every one
of the eleven fields must travel the whole way: `TARGET_FIELDS` → `RowData` →
`processRows` → import payload → `BulkLeadInput` → the SQL. Count the columns
against the placeholders before you run anything.

**4. Do not change validation, dedup or the mandatory gate.** `validateRow` must
still fail only on blank company name or unusable phone. Deduplication must
still key on normalised phone and lowercased company name only — the new fields
must not affect it. The Step-2 "Validate Rows" button must still be blocked
only by `company_name` and `contact_phone` being unmapped.

## Step 1 — report only, no changes

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD` and
   `git status -s` (report, do not clean).
2. The full `TARGET_FIELDS` array in `telecaller-app/lib/csv.ts`.
3. The `RowData` type and the `processRows` field-extraction block in
   `telecaller-app/components/CsvUploadModal.tsx`, with line numbers.
4. The `BulkLeadInput` type and the full `INSERT INTO leads (...) VALUES (...)`
   statement in `telecaller-app/actions/bulkCreateLeads.ts`, with line numbers.
   State how many columns and how many placeholders it currently has.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** these three files:

**`telecaller-app/lib/csv.ts`**
- Extend `TARGET_FIELDS` to the eleven entries above, in the order listed
  (mandatory two first, then the rest). `required: true` only on
  `company_name` and `contact_phone`.
- Give each new field sensible `autoGuesses`, lowercase, e.g.
  - `company_website`: `website`, `company website`, `url`, `web`, `site`, `company_website`
  - `industry`: `industry`, `sector`, `vertical`, `industry_label`
  - `job_description`: `job description`, `description`, `jd`, `job details`, `advert`, `ad text`, `job_description`
  - `role_titles`: `role`, `roles`, `role titles`, `job title`, `job titles`, `position`, `vacancy`, `role_titles`
  - `contact_source`: `source`, `lead source`, `origin`, `referred by`, `contact_source`
- Careful: `contact_title` already guesses `title` and `role`. Keep the existing
  entries' guesses as they are and make sure the auto-guess still assigns each
  CSV header to at most one field — first match wins, which is the existing
  behaviour.

**`telecaller-app/components/CsvUploadModal.tsx`**
- Add the five new keys to the `RowData` type and to the per-row extraction in
  `processRows`, same `String(rawRow[fieldMap.x] || '').trim()` pattern.
- Add them to the object built in `handleImport`, passing `null` when the
  trimmed value is empty (same as the existing optional fields).
- The preview table columns stay as they are — do not widen it to eleven
  columns. The mapping step is where the user confirms the mapping.
- The downloadable template is generated from `TARGET_FIELDS`, so it will pick
  the new headers up automatically; **update the hardcoded sample row** so it has
  the same number of values as headers, otherwise the template is malformed.

**`telecaller-app/actions/bulkCreateLeads.ts`**
- Extend `BulkLeadInput` with the five new optional fields.
- Parse `role_titles` per trap 1 and resolve `contact_source` per trap 2.
- Extend the `INSERT` column list and placeholders so all eleven map through.
  `company_key`, `origin`, `brand`, `status` stay exactly as they are.
- Server-side validation is unchanged: company name and phone only.

Then run from `/root/projects/lead-manger/telecaller-app` and paste the real
output of each with its exit code:

```
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```
(not `npx tsc` — it resolves to an unrelated package in this clone)

```
grep -c "key: '" lib/csv.ts
```
must print `11`.

```
grep -n "required: true" lib/csv.ts
```
must show exactly two lines.

Also state, in your reply, the column count and the placeholder count of the new
INSERT statement, and confirm they are equal.

## Step 3 — commit to `main`

Wait for Claude's approval, then stage **only** the three files by explicit path
and commit to `main`, then push. Report the hash and `git show --stat HEAD`; it
must list exactly three files. If the push is rejected because `main` moved, use
`git pull --rebase origin main` and push again. Never force-push.

## Acceptance

1. `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` exits `0`.
2. `grep -c "key: '" lib/csv.ts` prints `11`.
3. `grep -n "required: true" lib/csv.ts` shows exactly two lines
   (`company_name`, `contact_phone`).
4. The INSERT column count equals the placeholder count, stated in your reply.
5. `git show --stat HEAD` lists exactly the three files, and `git status -s`
   still shows any pre-existing `jd-lead-newspaper/` changes untouched.
