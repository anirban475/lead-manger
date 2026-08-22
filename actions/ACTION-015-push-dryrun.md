# ACTION-015 — Push dry run

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Databases: `leads` and `marketing_analytics`, both on container `shared-postgres`, user `admin`

Phase 1 of the Lead Push to Mystrika build. Phase 0 and 0.5 are merged and verified:
`lead-manger` `18e01f7`, `marketing-360` `41f3a8d` and `266e6da`.

**This script never sends anything. It has no write path of any kind. It reads two databases and
prints a report.**

## Why this exists

The push service will decide who gets emailed. Before it is allowed to do that, we need to see its
decisions on real data and compare them against what the current n8n workflows would pick. A
difference we cannot explain is a bug we have not found yet.

Two pieces of logic have never run against real data and are the actual subject of this test:

1. **The eligibility funnel.** Four filters, including a suppression check that the live workflows
   do not perform at all. Four leads currently match a suppressed email and can be re-emailed today.
2. **Field derivation from campaign copy.** Required merge fields are read out of each campaign's
   own emails rather than hand-maintained. This has never been executed.

`routing_rule` is empty and no campaign has a `segment_key`, so nothing can be routed yet. That is
expected. This dry run measures what is knowable now and states plainly what is blocked.

## Step 1 — report only, no code

1. Confirm both databases are reachable from a Python process on the VPS and say how you connect.
   `psql` through `docker exec` is the house pattern; follow it.
2. `SELECT state, count(*) FROM campaign_registry GROUP BY 1;`
3. `SELECT count(*) FROM routing_rule;` and
   `SELECT count(*) FROM campaign_registry WHERE segment_key IS NOT NULL;`
4. Note the brand casing difference: `leads.brand` is lowercase (`amatec`, `jobdrive`),
   `campaign_registry.brand` is Title Case (`Amatec`, `JobDrive`). Say how you will map them.
   **Do not normalise either table.**
5. `SELECT campaign_name, count(*) FROM campaign_copy GROUP BY 1 ORDER BY 1;`

Report key names only where credentials are involved. Never print a value, not even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build `tools/push_dryrun.py`

Read only. No `INSERT`, no `UPDATE`, no `DELETE`, no `ALTER`, anywhere in the file. No HTTP calls.

### 2a. Eligibility funnel

For each brand, start from every row in `leads` and apply these in order, reporting the count
surviving each stage so the funnel is visible:

| # | Filter |
|---|---|
| 1 | `contact_email` present, and not `''` or `'-'` |
| 2 | Not present in `leads.suppression` by email, matched on `lower(trim(...))` |
| 3 | `'<brand>' = ANY(eligible_brands)`. **Not** `brand = '<brand>'` |
| 4 | No `push_ledger` row for this `contact_key` against a campaign whose `state` is `ready` or `running` |

`contact_key` is `lower(trim(contact_email))`. `push_ledger` is empty today, so filter 4 will remove
nothing. Implement it properly anyway and report zero.

### 2b. Field derivation

For every campaign in `campaign_registry` whose `state` is `ready` or `running`:

1. Read every row in `campaign_copy` for it, joining on `campaign_id` where present and falling
   back to `campaign_name`.
2. Extract every merge tag from `subject` and `body` with `\{\{\s*([^}]+?)\s*\}\}`.
3. Normalise each tag: lowercase, trim, collapse internal whitespace.
4. **Validity checks. These block a whole campaign, not one lead:**
   - a tag whose captured text contains a space is invalid. Mystrika field names cannot contain
     spaces, so it can never merge. Report the campaign, step, variation and the exact tag.
   - a row whose `body` is null or empty blocks the campaign. Report it.
5. Resolve each valid tag to a source, in this order:
   - tier 1, the known-defaults table below
   - tier 2, exact match on a `leads` column name after normalising
   - tier 3, unresolved. Report it. The campaign is blocked until a human maps it.

Known defaults:

| tag | source |
|---|---|
| `company` | `company_name`, with `[TAGS]` stripped |
| `role` | `role_group`, translated to plain English |
| `city` | `city` |
| `name`, `fname`, `first_name` | first word of `contact_name` |
| `apply_count` | `apply_count` |

Then, for each campaign with a fully resolved tag set, count how many leads from that brand's
eligible pool could actually fill **every** tag, and how many would be held and for which missing
field.

### 2c. Comparison against the live workflows

Reproduce the two live selection queries exactly as they stand today and report the counts:

- JobDrive, workflow `1Uchg1PNp9eCqSVr`: `contact_email` non-empty, `mystrika_synced IS NULL`,
  `brand = 'jobdrive'`, ordered by score, limit 200
- Amatec, workflow `AmatecMystrika01`: `brand = 'amatec'`, `contact_email` non-empty,
  `mystrika_synced IS NULL`, `contact_source = 'apollo_person'`, `status = 'new'`,
  `email_catchall IS NOT TRUE`

Report, per brand: how many the old query picks, how many the new funnel picks, and **every lead
that appears in one and not the other, with the reason**. That difference list is the single most
important output of this task.

### 2d. Report format

Plain text to stdout. Sections in this order:

1. Eligibility funnel per brand, count surviving each stage
2. Campaigns considered, with state, and why each was included or skipped
3. Per campaign: tags found, tags resolved, tags unresolved, validity failures
4. Per campaign: leads that could be filled, leads that would be held grouped by missing field
5. Routing status. Since `routing_rule` is empty, state plainly that every lead would be **held and
   reported**, and that this is correct behaviour rather than a failure
6. The old-versus-new difference list from 2c
7. A closing summary of what is blocked and what a human must supply

Exit `0` when the report is produced, `1` on any error.

### The trap

**There must be no way for this script to write anything.** Not a debug flag, not an `--apply`
switch, not a commented-out block. If you find yourself adding one for a future phase, stop and say
so instead. A read-only tool that grows a write path is how a dry run stops being a dry run.

`grep -nE "INSERT|UPDATE|DELETE|ALTER|DROP|COMMIT|requests|urllib|httpx" tools/push_dryrun.py`
must return nothing but false positives you can explain.

### Other non-goals

Do not modify anything in `sql/migrations/` or `tools/` that already exists. Do not touch
`marketing_analytics` beyond reading. Do not open or edit any n8n workflow. Do not call the
Mystrika API.

Then run it once and paste the real output in full. Not a summary.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `tools/push_dryrun.py` to `main`. Remember `.gitignore` line 31 is `*.py`, so `git add -f`.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 is verified independently.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Read-only against both databases. See the trap.
- Do not modify, deactivate or open any n8n workflow.
- Do not restart, stop or reconfigure any pm2 service.
- Do not call any external API.
- **One step per reply.** Finish a step, report, and wait.

## Acceptance

Done when:

1. `python3 tools/push_dryrun.py` runs and exits `0`.
2. The report shows the eligibility funnel per brand with a visible count at each stage.
3. The suppression filter removes a non-zero number of leads, since 4 currently match.
4. At least one campaign reports a merge tag containing a space, since `{{Company Name}}` is live
   in four Amatec campaigns.
5. The old-versus-new difference list is present and every difference carries a reason.
6. The grep in the trap section returns nothing unexplained.
7. The script is pushed to `main`.
