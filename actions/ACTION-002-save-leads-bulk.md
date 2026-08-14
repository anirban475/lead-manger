# ACTION-002 — save_leads_bulk on the lead-scraper MCP

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The Jobdrive newspaper radar saves one lead per `save_leads` call. On the 2026-08-13 run that meant 130 sequential MCP calls, which cost **350,000 tokens, 28% of the entire run**, for work that involves no judgement at all: the 23 arguments per row were already computed and sitting in a JSON file before the first call was made.

The cost is not the SQL. It is that each call is a separate agent turn, and every turn re-reads the whole conversation, so 26 saves cost far more than 26 times one save. Measured: judging an ad costs about 1.4k tokens, writing a finished row costs 2.7k.

It also caps the pipeline. Run 2 on 2026-08-12 found 369 qualifying companies and saved only 46, deferring 323, and wrote into the state doc that "one `save_leads` call per company does not scale to 369 rows in a single session". A bulk endpoint removes that ceiling.

One call taking an array of 130 rows costs roughly 10k tokens instead of 350k.

## Hard context you need before you start

`save_leads` lives in n8n workflow `zUbadDjZ9PfMR8av` ("Indeed Scraper MCP"), served at `https://n8n.amatec.in/mcp/lead-scraper`. It is **active and in production**. Five of its nodes share one Postgres credential, and Bhratti's telecaller cockpit plus both lead radars depend on them. Unbinding that credential breaks the lead pipeline.

**There is already a proven safe pattern for this exact job**: `jd-lead-newspaper/add_newspaper_mcp_tool.py`. It reads nodes and connections out of `workflow_entity`, appends a node in Python, asserts the credential-bearing node count is unchanged, backs up to JSON, then writes back through `psql` variables. Model the new script on it. Do not invent a different approach, and do not use the n8n Workflow SDK, which cannot bind an existing credential.

## Step 1 — report only, no changes

Read and report:

1. The full `query` and `options.queryReplacement` of the `save_leads` node in workflow `zUbadDjZ9PfMR8av`.
2. How many nodes the workflow has, and how many carry a `credentials` block. Report **credential key names only, never a value, not even partially.**
3. Whether a node named `save_leads_bulk` already exists.
4. Whether `/root/projects/lead-manger/jd-lead-newspaper/zUbadDjZ9PfMR8av_backup.json` exists, and its mtime.
5. Confirm the `leads` table has a unique constraint or unique index on `company_key`. Paste the constraint definition. `ON CONFLICT (company_key)` fails without it.

Stop after reporting. Write nothing.

## Step 2 — build the script, dry run only

Create `jd-lead-newspaper/add_save_leads_bulk.py`, modelled on `add_newspaper_mcp_tool.py`.

It makes exactly two changes to workflow `zUbadDjZ9PfMR8av`:

**Change A. Append a new node `save_leads_bulk`**, type `n8n-nodes-base.postgresTool`, `typeVersion` 2.6, `operation` `executeQuery`, `descriptionType` `manual`, position `[336, 656]`, a fresh uuid4 id. Copy the `credentials` block from the existing `save_leads` node **by reference, unchanged**. Connect it to `MCP Server Trigger` on `ai_tool`, index 0, exactly as the other tool nodes are.

`query`:

```sql
INSERT INTO leads (company_key, company_name, industry, size, city, roles_count, role_titles, posted_date, job_urls, contact_phone, contact_email, contact_source, company_website, score, tier, source_query, apply_count, role_group, industry_label, contact_name, contact_title, contact_linkedin, brand)
SELECT DISTINCT ON (r.company_key)
  r.company_key, r.company_name, r.industry, r.size, r.city,
  NULLIF(r.roles_count,'')::int,
  CASE WHEN r.role_titles LIKE '%|%' THEN string_to_array(r.role_titles,'|') ELSE string_to_array(r.role_titles,',') END,
  NULLIF(r.posted_date,'')::date,
  string_to_array(r.job_urls,','),
  r.contact_phone, r.contact_email, r.contact_source, r.company_website,
  NULLIF(r.score,'')::int, r.tier, r.source_query,
  NULLIF(r.apply_count,'')::int,
  r.role_group, r.industry_label, r.contact_name, r.contact_title, r.contact_linkedin, r.brand
FROM jsonb_to_recordset($1::jsonb) AS r(
  company_key text, company_name text, industry text, size text, city text,
  roles_count text, role_titles text, posted_date text, job_urls text,
  contact_phone text, contact_email text, contact_source text, company_website text,
  score text, tier text, source_query text, apply_count text, role_group text,
  industry_label text, contact_name text, contact_title text, contact_linkedin text, brand text)
ORDER BY r.company_key
ON CONFLICT (company_key) DO UPDATE SET
  roles_count = EXCLUDED.roles_count, role_titles = EXCLUDED.role_titles,
  posted_date = EXCLUDED.posted_date, job_urls = EXCLUDED.job_urls,
  score = EXCLUDED.score, tier = EXCLUDED.tier,
  source_query = COALESCE(leads.source_query, EXCLUDED.source_query),
  apply_count = EXCLUDED.apply_count, role_group = EXCLUDED.role_group,
  industry_label = EXCLUDED.industry_label,
  contact_name = COALESCE(leads.contact_name, EXCLUDED.contact_name),
  contact_title = COALESCE(leads.contact_title, EXCLUDED.contact_title),
  contact_linkedin = COALESCE(leads.contact_linkedin, EXCLUDED.contact_linkedin),
  updated_at = now()
RETURNING company_key, status
```

`options.queryReplacement`:

```
={{ $fromAI("rows", "JSON array of lead objects, each carrying the same 23 fields as save_leads. Keep to 200 per call.", "string") }}
```

`toolDescription`:

```
Upsert MANY leads in ONE call. Input: rows, a JSON array of objects each carrying the same 23 fields as save_leads. Same upsert semantics on company_key, never overwrites an existing status. Duplicate company_key values inside one batch are collapsed. ALWAYS set brand explicitly on every object. Prefer this over save_leads whenever saving more than one company.
```

Two properties of that SQL that must not be edited away:

- `DISTINCT ON (r.company_key)` with `ORDER BY r.company_key` is load bearing. Without it a repeated key inside one batch throws `ON CONFLICT DO UPDATE command cannot affect row a second time`.
- The `DO UPDATE SET` list deliberately omits `status`, `city`, `industry`, `size`, `contact_phone`, `contact_email`, `contact_source`, `company_website` and `brand`, matching the single-row node exactly. Do not add them.

**Change B. Flatten the dead nested CASE in the existing `save_leads` query.** It currently reads:

```sql
CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE string_to_array($7, ',') END END
```

The inner test can never be true when the outer one is false, so the middle branch is unreachable. Replace with:

```sql
CASE WHEN $7 LIKE '%|%' THEN string_to_array($7, '|') ELSE string_to_array($7, ',') END
```

Behaviour is identical. This is a readability fix on a query that has already been patched twice. **Change nothing else in that node.**

Script requirements:

- `--dry-run` flag that prints the diff and writes nothing, same as the existing script.
- Abort with exit 1 if `save_leads_bulk` already exists.
- Abort with exit 1 if the count of nodes carrying a `credentials` block differs before and after.
- Abort with exit 1 if the new node's `credentials` block is not byte-identical to `save_leads`.
- Abort with exit 1 if the `save_leads` query after Change B is not exactly the original with the nested CASE flattened, that is, if anything other than that substring moved.
- Back up the current workflow JSON before any write.
- Exit 0 only when the REST reload returned 2xx.

Run it with `--dry-run` and paste the real output. Not a summary of the output.

## Step 3 — apply

Run the script for real. Paste the real output and the exit code.

**The trap, read this twice.** `add_newspaper_mcp_tool.py` falls back to toggling `workflow_entity.active` in Postgres when the REST reload fails, and exits 2. That toggle **does not reload n8n's in-memory state**. This has already produced a run where every acceptance criterion passed while the thing being built was absent from the running system.

**Exit code 2 is a failure for this task.** If the script exits 2, stop, report it, and do not proceed to Step 4. Do not restart the n8n container to work around it. That is a Stop and ask condition.

## Step 4 — prove it is live, then clean up after yourself

Liveness is proved through the MCP endpoint, not the database.

1. Call `tools/list` on `https://n8n.amatec.in/mcp/lead-scraper` and paste the raw response. `save_leads_bulk` must appear. **A row in `workflow_entity` is not acceptance.** If the tool is absent from `tools/list`, the node is not live, whatever the database says.
2. Call `save_leads_bulk` through that endpoint with exactly two rows, `company_key` values `zztest_bulk_a` and `zztest_bulk_b`, `brand` `jobdrive`, `role_titles` `Accountant|Sales Executive (GST, Tally)` on the first row so the pipe split and the internal comma are both exercised, and any plausible values elsewhere. Paste the raw response. Expect two rows returned.
3. Verify with `SELECT company_key, array_length(role_titles,1), role_titles FROM leads WHERE company_key LIKE 'zztest_bulk_%';` and paste it. Row A must show `array_length` of 2, with `Sales Executive (GST, Tally)` intact as one element rather than shredded on the internal comma.
4. Call it again with the same two rows plus a third, `zztest_bulk_a` repeated inside the same array. It must not error. Paste the output. This is the `DISTINCT ON` check.
5. `DELETE FROM leads WHERE company_key LIKE 'zztest_bulk_%';` and paste the reported row count. Then re-run the SELECT from point 3 and paste the empty result. **Do not leave test rows in the production leads table.**

## Step 5 — commit

Only after the Step 4 output is posted and looks right:

- Commit `jd-lead-newspaper/add_save_leads_bulk.py` and the workflow backup JSON.
- Add a short section to `jd-lead-newspaper/README.md` recording that `save_leads_bulk` exists, that exit code 2 from these scripts means the change is in the database but not live, and that acceptance for any n8n node change is `tools/list`, never a database row.
- Push to `origin`. Report the commit hash.

## Step 6 — merge and clean up

Claude does this, not Antigravity, and only after Step 5 has been verified independently against GitHub.

- Merge to `main`.
- Delete this brief from `actions/`.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not edit `add_newspaper_mcp_tool.py` or `fix_role_titles_split.py`. Model the new script on the first, do not modify it.
- Do not restart, stop or reconfigure the n8n container, the `shared-postgres` container, or the Slack listener.
- Do not touch any node other than `save_leads` and the new `save_leads_bulk`.
- Report key names only where credentials are involved. Never print a value, not even partially. This includes the n8n API key the reload path reads from `user_api_keys`, and the Postgres password.
- **One step per reply.** Finish a step, report, and wait.

## Acceptance

Done when `tools/list` on `https://n8n.amatec.in/mcp/lead-scraper` returns `save_leads_bulk`, a two-row call through that endpoint returns two rows with `role_titles` split on the pipe and the bracketed comma preserved, a repeated key inside one batch does not error, the test rows are deleted and shown gone, the script exits 0, and the work is pushed to `main`.
