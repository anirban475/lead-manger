# ACTION-001 — Add `fetch_newspaper_ads` to the lead-scraper MCP

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The Jobdrive newspaper radar reads recruitment classifieds from ads2publish.com.
It currently fetches those pages with WebFetch, which passes every page through a
summarising model before the radar sees it, and **that model silently drops ads**.
Ads2Publish numbers its ads sequentially, and the extractions had gaps: Deccan
Chronicle jumped from Ad 2 to Ad 4, Namasthe Telangana from Ad 4 to Ad 7, Kannada
Prabha skipped Ad 4, and about a dozen other papers did the same. Those ads were
fetched and then thrown away before anyone judged them. The source is a rolling
window, so the lost leads are unrecoverable.

A replacement n8n workflow already exists and is verified: **"Newspaper Radar —
Raw Ad Fetch"**, id `aeWlxXTWGRHyGehZ`, webhook
`POST https://n8n.amatec.in/webhook/newspaper-ads` with body `{"slug":"..."}`.
It fetches raw HTML server-side and parses it with no model in the path. Tested
across seven publications on 2026-08-12: all returned 10 of 10 ads with
`missingIndices: []`, including the three that previously had gaps.

**The remaining gap is exposure.** The radar can only consume it if it is an MCP
tool, because an MCP tool response is returned raw. If the radar instead fetched
that webhook with WebFetch, the response would be summarised and the exact data
loss would come straight back.

So one node must be added to the lead-scraper MCP workflow, id
`zUbadDjZ9PfMR8av`, named "Indeed Scraper MCP" in the n8n UI.

**Why this is not a two-minute job.** That workflow serves 11 live MCP tools.
Nine of them carry credentials: Apify `httpHeaderAuth` on five HTTP nodes, and a
Postgres credential on four. The n8n MCP's own `get_workflow_details` returns
those nodes with **no credential IDs at all**, so any full-replace write built
from that output silently strips authentication off nine working tools. That has
been verified, it is not a theory. Two UI attempts to add the node by hand did
not stick, and browser automation could not drive the n8n editor canvas because
it never reaches `document_idle`.

## Step 1 — report only, no changes

Investigate and report. Change nothing.

1. n8n version, and how n8n is run (container name, compose file path if any).
2. Is the n8n **public REST API** enabled? If an API key exists anywhere in the
   environment or config, report only that one exists and what it is called.
   **Never print the value, not even partially, not even the first characters.**
3. In the n8n Postgres database, for workflow `zUbadDjZ9PfMR8av`: how many nodes
   are in the `nodes` JSON, and **how many of them have a `credentials` key**.
   Report the node names that have credentials. Do **not** print credential IDs
   or any credential contents.
4. Does this n8n keep workflow versions? Report whether tables such as
   `workflow_history` exist, and what `versionId` / `activeVersionId` currently
   are for this workflow.
5. Based on 1 to 4, **propose the safest write path** and say why. The two
   candidates are (a) the n8n REST API with the full workflow object read back
   and re-sent with credentials intact, or (b) a direct database update of the
   `nodes` and `connections` JSON. State which you recommend and what would have
   to be true for it to be safe.

Stop after reporting. Do not write anything yet. Do not restart anything.

## Step 2 — build the change script, dry run only

Create `jd-lead-newspaper/add_newspaper_mcp_tool.py` (or `.sh` if that is a
better fit for the path chosen in Step 1).

It must:

- Read the current workflow `zUbadDjZ9PfMR8av` in full, including credentials.
- Add exactly one node and one connection. Nothing else changes.
- Preserve every existing node byte for byte, including every `credentials`
  block.
- Support `--dry-run`, which prints what would change and writes nothing.
- Exit 0 on success, non-zero on any failure.

The node to add, exactly:

```json
{
  "parameters": {
    "toolDescription": "Fetch one day's recruitment ads for a single publication from Ads2Publish, parsed server-side from raw HTML so no ads are lost. Input: slug (e.g. times-of-india, dainik-jagran, eenadu). Returns classifiedCount, displayCount, highestAdIndex, missingIndices (should always be empty; a non-empty value means the source itself skipped an ad number) and ads[] with adType, adIndex, body, category (full path), email, phone. Use this instead of WebFetch, which silently drops ads.",
    "method": "POST",
    "url": "https://n8n.amatec.in/webhook/newspaper-ads",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ slug: $fromAI(\"slug\", \"Ads2Publish publication slug, e.g. times-of-india or dainik-jagran\", \"string\") }) }}",
    "options": { "timeout": 60000 }
  },
  "name": "fetch_newspaper_ads",
  "type": "n8n-nodes-base.httpRequestTool",
  "position": [1360, 528],
  "typeVersion": 4.4
}
```

Give it a fresh UUID for `id`. It takes **no credentials**, exactly like the
existing `get_company_size` node, which is the correct model to copy.

The connection to add, alongside the existing eleven:

```json
"fetch_newspaper_ads": { "ai_tool": [[{ "node": "MCP Server Trigger", "type": "ai_tool", "index": 0 }]] }
```

Then run it with `--dry-run` once and **paste the real output**, not a summary.
The dry run must show the node count going from 12 to 13, the connection count
going from 11 to 12, and the count of nodes carrying credentials staying exactly
the same as Step 1 reported.

## Step 3 — apply and verify

Only after the Step 2 dry-run output is posted and looks right.

Run the script for real, then verify and paste actual output for each:

1. `fetch_newspaper_ads` node exists, exactly once.
2. Nodes carrying credentials is **the same number as Step 1 reported**. If this
   number dropped by even one, you have broken live tools: stop, restore, and
   report immediately.
3. The workflow is still `active`.
4. Functional test of the underlying webhook:
   `curl -s -m 60 -X POST http://localhost:5678/webhook/newspaper-ads -H 'Content-Type: application/json' -d '{"slug":"times-of-india"}'`
   Report `classifiedCount`, `displayCount` and `missingIndices` only, not the
   whole body.

If the change requires n8n to reload to pick it up, prefer toggling this single
workflow's active state over restarting the n8n process. **Do not restart the n8n
container**, other workflows depend on it. If a full restart is the only option,
stop and report rather than doing it.

## Step 4 — commit

Only after Step 3 output is posted:

- Commit the script to `main` with a message saying what it does and why.
- Push to `origin`.
- Report the commit hash.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and the n8n workflow named above.
  Touch nothing else on the VPS.
- Do **not** modify any node other than by adding the one new node. Do not edit
  `save_leads`, `get_leads`, `log_run`, `get_run_history`, `get_query_yield`,
  `run_indeed_scrape`, `run_actor`, `get_company_size`, `start_actor`,
  `get_run_status` or `get_dataset_items`.
- Do **not** use the n8n MCP `update_workflow` tool or any SDK re-emit. Both are
  full replaces built from output that omits credential IDs, and both will strip
  authentication off nine live tools.
- Do **not** restart, stop or reconfigure the n8n container, the Postgres
  container, or any other service.
- Do **not** print any credential value, API key or token, not even partially.
  Names and counts only.
- Back up the workflow's current `nodes` and `connections` JSON to a file before
  any write, and report the path.
- **One step per reply.** Finish a step, report, and wait.

## Acceptance

Done when:

```
docker exec shared-postgres psql -U admin -d n8n -Atc "SELECT count(*) FROM jsonb_array_elements(nodes::jsonb) n WHERE n->>'name'='fetch_newspaper_ads';"
```

prints `1`, exit code 0, **and** the count of credential-bearing nodes is
unchanged from Step 1, **and** the workflow is still active, **and** the script
is pushed to `main`.
