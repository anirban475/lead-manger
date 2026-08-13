# ACTION-002 — Fix role_titles comma-split in save_leads, and backfill

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## CORRECTION, issued after Step 1. Read this before Step 2.

Step 1 reported **85** rows where `roles_count <> array_length(role_titles, 1)`.
That number is correct and it broke the brief, because **`roles_count` mismatch is
not the signature of this bug**. Two unrelated things produce it.

| Source | Pattern | Cause |
|---|---|---|
| Newspaper | `roles_count` **below** array length | The split bug. Real corruption |
| Naukri, Amatec | `roles_count` **above** array length | By design. `roles_count` is open positions, `role_titles` holds the representative title |

Examples of the second kind, which are **correct data and must not be touched**:

```
naukri_biomatrixhealthcare  roles_count 5  {"Officer to Sr. Officer - QC Microbiology"}
amatec_kaleidoscopeaba      roles_count 9  {"Center Operations Coordinator"}
```

Repairing those would destroy the open-positions signal that feeds Naukri scoring.

**The correct detector is bracket imbalance, not count mismatch.** A row is
corrupted when any element of `role_titles` has an unequal number of `(` and `)`:

```sql
EXISTS (SELECT 1 FROM unnest(l.role_titles) t
        WHERE length(t) - length(replace(t,'(','')) 
           <> length(t) - length(replace(t,')','')))
```

That returns **26 rows: 17 newspaper and 9 non-newspaper.** The 9 non-newspaper
rows are genuinely corrupted by the same split and **are in scope**.

Two rules follow, and they override anything below that disagrees:

1. **Repair scope is the 26 bracket-imbalanced rows only.** Brand is irrelevant,
   the bug is not brand specific. Do not touch a row because its `roles_count`
   disagrees with its array length.
2. **Recompute `roles_count` only for rows whose `company_key` starts with `np`.**
   For every other row, rejoin the fragments and leave `roles_count` exactly as it
   is.

---

## Why this exists

The `save_leads` tool on n8n workflow `zUbadDjZ9PfMR8av` writes role titles with:

```sql
string_to_array($7, ',')
```

That splits on **every** comma, including commas inside parentheses. A single role
becomes several fragments.

Real corruption in production today:

| Ad text | Stored as |
|---|---|
| `Welfare Officer (Factory rules, Labour law)` | `{"Welfare Officer (Factory rules"," Labour law)"}` |
| `Marketing Engineer (2 positions, BE Mech)` | `{"Marketing Engineer (2 positions"," BE Mech)"}` |
| `Head Accounts (TDS, GST, BS, Banking and Finance ops)` | 4 fragments |

Two things break because of it, and neither is visible from the app.

1. **The role suitability filter reads fragments.** The Newspaper Radar Playbook
   rejects ads whose roles are walk-in hires, matching on words including
   `labour`. The fragment `" Labour law)"` matches. **Astra MWP, a Welfare
   Officer vacancy, gets flagged as unskilled labour.** It survived only because
   a human read the row before the delete ran.
2. **`roles_count` is wrong on newspaper rows.** It feeds the overload score, so
   those leads are scored off a number that was never observed.

`job_urls` uses `string_to_array($9, ',')` and carries the same class of bug. It is
**out of scope** for this brief. Report it if you see it, do not change it.

## Step 1 — report only, no changes

DONE. Verified independently. `string_to_array($7, ',')` confirmed at index `$7`,
credential-bearing node count confirmed at **10**, matching the known figure.

## Step 2 — build the fix script

Create `jd-lead-newspaper/fix_role_titles_split.py`.

It must do two independent things, each behind its own function, so either can be
run alone:

**A. Patch the `save_leads` node.** Replace `string_to_array($7, ',')` with a
delimiter-tolerant form that prefers a pipe and falls back to comma:

```sql
CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|')
     ELSE string_to_array($7, ',') END
```

Backward compatibility is the point. The Naukri radar also calls `save_leads` and
still passes commas. It must keep working unchanged.

Requirements:

- Patch **only** the `query` string of the node named `save_leads`. Do a targeted
  in-place edit of that one JSON value. **Do not replace the workflow document.**
- Every other node, and every credential reference on every node, must be byte
  identical before and after. Prove it: print the credential-bearing node count
  before and after, and assert both equal **10**.
- After the DB write, reload the workflow through the n8n API:
  `POST /api/v1/workflows/zUbadDjZ9PfMR8av/deactivate` then `/activate`.
  A raw `UPDATE workflow_entity SET active` does **not** reload n8n's in-memory
  activation manager. That exact mistake made a previous run report success on a
  change that was not live.

**B. Backfill the 26 bracket-imbalanced rows.** Rejoin fragments by bracket
balance: walk the array, and while the accumulated string has more `(` than `)`,
append the next element back with `, `.

Requirements:

- Select rows with the **bracket-imbalance detector in the correction above**.
  Never with a `roles_count` comparison.
- Set `roles_count = array_length(role_titles, 1)` **only** where
  `company_key LIKE 'np%'`. Leave `roles_count` untouched on every other row.
- Write every affected row to a backup table `role_titles_backup` first,
  including the original array and a timestamp.
- Run in a transaction. Print the before and after array for **every** row it
  changes, not a sample.
- Idempotent. Running it twice must change zero rows on the second pass.
- Exit 0 on success, non-zero on any assertion failure.
- **Non-goals:** do not touch `job_urls`. Do not touch a row whose brackets are
  already balanced. Do not touch `roles_count` on non-newspaper rows.

Then run it once and paste the real output. Not a summary of the output.

## Step 3 — verify the fix is live

Prove the node change is actually running, not just written to the database:

- Call `tools/list` on the Lead Scraper MCP endpoint and confirm `save_leads` is
  still present and the workflow still exposes all its tools.
- Insert one throwaway row through `save_leads` with a pipe-delimited
  `role_titles` value containing a comma inside brackets, for example
  `Welfare Officer (Factory rules, Labour law)|Junior Accountant`. Confirm it
  lands as exactly two array elements. Then delete the throwaway row and confirm
  it is gone.
- Insert a second throwaway row with a **comma-delimited, no-pipe** value to prove
  the fallback branch still works for the Naukri radar. Then delete it.

Paste the raw output of each check.

## Step 4 — commit

Only after the Step 2 and Step 3 output is posted and looks right:

- Commit `jd-lead-newspaper/fix_role_titles_split.py` to `main` with a message
  saying what it does and why.
- Push to `origin`.
- Report the commit hash.

## Step 5 — merge and clean up

Claude does this, not Antigravity, and only after Step 4 has been verified
independently through GitHub:

- Merge to `main`.
- Delete this brief from `actions/`.
- Move two things into durable docs before deleting: the delimiter change into the
  Newspaper Radar Playbook `save_leads` field map, which currently documents
  `role_titles` as comma separated, and the finding that `roles_count` means open
  positions on Naukri and Amatec rows but distinct roles on newspaper rows.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and the two databases named above.
  Touch nothing else on the VPS.
- Do not edit any node in workflow `zUbadDjZ9PfMR8av` other than `save_leads`.
- Do not edit workflow `aeWlxXTWGRHyGehZ` (Newspaper Radar Raw Ad Fetch).
- Do not restart, stop or reconfigure the `n8n` container. Deactivate and
  reactivate the single workflow through the API only.
- Do not delete any lead row. The backfill updates, it never deletes.
- **One step per reply. Finish a step, report, and wait.**

## Acceptance

Done when:

1. `python3 jd-lead-newspaper/fix_role_titles_split.py --verify` runs, reports
   **zero rows with bracket imbalance in `role_titles`**, and exits 0.
2. The count of rows where `roles_count <> array_length(role_titles, 1)` is still
   **non-zero and unchanged for non-newspaper rows**. Those are correct data. If
   that count drops to zero, the script over-reached and the run has failed.
3. The credential-bearing node count on workflow `zUbadDjZ9PfMR8av` is **10**
   after the change, and `tools/list` still returns every tool.
4. Both round trips in Step 3 pass: pipe input gives two elements, comma input
   still splits as before.
5. The script is pushed to `main`.
