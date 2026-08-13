# ACTION-002 — Fix role_titles comma-split in save_leads, and backfill

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

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
2. **`roles_count` is wrong.** 18 of 161 newspaper rows have `roles_count = 1`
   while `array_length(role_titles, 1)` is 2 to 4. `roles_count` feeds the
   overload score, so those leads are scored off a number that was never
   observed.

Known affected rows include: Astra MWP, Rotocast Group, Advaithaa, Powertex Tools,
GRC-RLS, IMTS Solutions, Allied Instruments and Thermocouples, Route Auto Electric,
Inmasa Technamic, V-Vanguard, Arunodaya Print Pack, Evergreen Foods & Snacks.

`job_urls` uses `string_to_array($9, ',')` and carries the same class of bug. It is
**out of scope** for this brief. Report it if you see it, do not change it.

## Step 1 — report only, no changes

Read the current state and report:

1. The full `parameters.query` of the `save_leads` node in workflow
   `zUbadDjZ9PfMR8av`, and confirm the exact `string_to_array` call and its
   parameter index.
2. How many nodes in that workflow carry a credential reference. Report the
   **count and the node names only**. This number matters: a previous run
   established that **10 of 12 tool nodes carry credentials**, and any write that
   replaces the workflow wholesale strips auth from all of them. If your count
   disagrees with 10, stop and say so before going further.
3. From the `leads` database, the exact count of rows where
   `roles_count <> array_length(role_titles, 1)`, and the same count restricted to
   `company_key LIKE 'np%'`.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

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
  before and after, and assert they match.
- After the DB write, reload the workflow through the n8n API:
  `POST /api/v1/workflows/zUbadDjZ9PfMR8av/deactivate` then `/activate`.
  A raw `UPDATE workflow_entity SET active` does **not** reload n8n's in-memory
  activation manager. That exact mistake made a previous run report success on a
  change that was not live.

**B. Backfill the corrupted rows.** Rejoin fragments by bracket balance: walk the
array, and while the accumulated string has more `(` than `)`, append the next
element back with `, `. Then set `roles_count = array_length(role_titles, 1)`.

Requirements:

- Write every affected row to a backup table `role_titles_backup` first,
  including the original array and a timestamp.
- Run in a transaction. Print the before and after array for **every** row it
  changes, not a sample.
- Idempotent. Running it twice must change zero rows on the second pass.
- Exit 0 on success, non-zero on any assertion failure.
- **Non-goal:** do not touch `job_urls`, do not touch any row where the array is
  already balanced, do not touch rows from other brands.

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
- Move the delimiter change into the Newspaper Radar Playbook `save_leads` field
  map before deleting, since the playbook currently documents `role_titles` as
  comma separated and that will now be wrong.

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
   zero rows where `roles_count <> array_length(role_titles, 1)`, and exits 0.
2. The credential-bearing node count on workflow `zUbadDjZ9PfMR8av` is the same
   after the change as before, and `tools/list` still returns every tool.
3. The pipe-delimited round trip in Step 3 produces exactly two array elements.
4. The script is pushed to `main`.
