# ACTION-001 — Add `fetch_newspaper_ads` to the lead-scraper MCP

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

**STATUS: COMPLETE, 2026-08-12.** Script committed as
`9aef582695c74e20fe14c77b6d79567249a8920b`. Tool is live, 12 tools on the MCP,
credential-bearing nodes 10 before and 10 after. Two corrections were made to
this document after execution, both marked below. Read them before rerunning
anything here.

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

> **CORRECTION, 2026-08-12.** This document originally said nine nodes carry
> credentials, with "Postgres credential on four". That is **wrong**. The real
> figure is **ten**: five Apify `httpHeaderAuth` and **five** Postgres. The
> figure matters because it is the safety invariant for the whole job. Had the
> run locked onto nine, a write that silently dropped one credential would have
> passed every downstream check and looked clean. Anyone rerunning this must
> re-derive the count with raw SQL rather than trusting any number written here.

Ten of the eleven tool nodes carry credentials. The n8n MCP's own
`get_workflow_details` returns those nodes with **no credential IDs at all**, so
any full-replace write built from that output silently strips authentication off
ten working tools. That has been verified, it is not a theory. Two UI attempts to
add the node by hand did not stick, and browser automation could not drive the
n8n editor canvas because it never reaches `document_idle`.

## Step 1 — report only, no changes

Investigate and report. Change nothing.

1. n8n version, and how n8n is run (container name, compose file path if any).
2. Is the n8n **public REST API** enabled? If an API key exists anywhere in the
   environment or config, report only that one exists and what it is called.
   **Never print the value, not even partially, not even the first characters.**
3. In the n8n Postgres database, for workflow `zUbadDjZ9PfMR8av`: how many nodes
   are in the `nodes` JSON, and **how many of them have a `credentials` key**.
   Report the node names that have credentials. Do **not** print credential IDs
   or any credential contents. **Derive this count from raw SQL output and paste
   it. Do not restate the number from the section above, which was wrong once.**
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

Write any backup **outside the repo**, or gitignore it. A workflow backup
contains `credentials` blocks with credential IDs and must never be committed.

## Step 3 — apply and verify

Only after the Step 2 dry-run output is posted and looks right.

Run the script for real, then verify and paste actual output for each:

1. `fetch_newspaper_ads` node exists, exactly once.
2. Nodes carrying credentials is **the same number as Step 1 reported**. If this
   number dropped by even one, you have broken live tools: stop, restore, and
   report immediately.
3. The workflow is still `active`.
4. **The tool is actually live on the MCP endpoint.** See the trap below. A
   database row is not proof. List the tools on the running MCP server and
   confirm `fetch_newspaper_ads` appears and the count went from 11 to 12.
5. Functional test:
   `curl -s -m 60 -X POST http://localhost:5678/webhook/newspaper-ads -H 'Content-Type: application/json' -d '{"slug":"times-of-india"}'`
   Report `classifiedCount`, `displayCount` and `missingIndices` only.

> **TRAP FOUND DURING EXECUTION, 2026-08-12. Read this.** The first attempt
> "reloaded" the workflow with `UPDATE workflow_entity SET active = false` then
> `true`. That is a raw column write. It does **not** touch n8n's in-memory
> activation manager, so the running process kept serving the old workflow. The
> database said the node was there, the workflow said `active = t`, and
> `tools/list` against the live endpoint still returned **11 tools with
> `fetch_newspaper_ads` absent**. Every acceptance criterion below passed while
> the tool was unusable.
>
> Worse, the functional test in item 5 hits `/webhook/newspaper-ads`, which
> belongs to the **other** workflow (`aeWlxXTWGRHyGehZ`) and already worked. It
> proves the fetch layer is healthy. It proves nothing about this change.
>
> The correct reload is n8n's own API:
> `POST /api/v1/workflows/{id}/deactivate` then `POST /api/v1/workflows/{id}/activate`.
> Both take no request body, so nothing in a payload can strip credentials,
> unlike a `PUT` or the `update_workflow` MCP tool.

If the change requires n8n to reload to pick it up, prefer the deactivate then
activate API over restarting the n8n process. **Do not restart the n8n
container**, other workflows depend on it. If a full restart is the only option,
stop and report rather than doing it.

## Step 4 — commit

Only after Step 3 output is posted:

- Commit the script to `main` with a message saying what it does and why.
- Push to `origin`.
- Report the commit hash.
- Confirm the pushed tree contains **no** backup or credential file.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and the n8n workflow named above.
  Touch nothing else on the VPS.
- Do **not** modify any node other than by adding the one new node. Do not edit
  `save_leads`, `get_leads`, `log_run`, `get_run_history`, `get_query_yield`,
  `run_indeed_scrape`, `run_actor`, `get_company_size`, `start_actor`,
  `get_run_status` or `get_dataset_items`.
- Do **not** use the n8n MCP `update_workflow` tool or any SDK re-emit. Both are
  full replaces built from output that omits credential IDs, and both will strip
  authentication off ten live tools.
- Do **not** restart, stop or reconfigure the n8n container, the Postgres
  container, or any other service.
- Do **not** print any credential value, API key or token, not even partially.
  Names and counts only.
- Back up the workflow's current `nodes` and `connections` JSON before any write,
  **outside the repo or gitignored**, and report the path.
- **One step per reply.** Finish a step, report, and wait.

## Acceptance

Done when:

```
docker exec shared-postgres psql -U admin -d n8n -Atc "SELECT count(*) FROM jsonb_array_elements(nodes::jsonb) n WHERE n->>'name'='fetch_newspaper_ads';"
```

prints `1`, exit code 0, **and** the count of credential-bearing nodes is
unchanged from Step 1, **and** the workflow is still active, **and** the live MCP
endpoint lists 12 tools including `fetch_newspaper_ads`, **and** the script is
pushed to `main`.

## Outcome, 2026-08-12

| Check | Result |
|---|---|
| Commit | `9aef582695c74e20fe14c77b6d79567249a8920b` |
| Credential-bearing nodes before | 10 |
| Credential-bearing nodes after | 10 |
| MCP tools before / after | 11 / 12 |
| `times-of-india` test | `classifiedCount 10`, `displayCount 2`, `missingIndices []` |

Not verified: a single end-to-end call *through* the MCP tool itself. The tool is
exposed and the underlying webhook returns correct data, but those were confirmed
separately rather than as one chain.

Script quality note: SQL is built by string interpolation with quote-doubling
rather than parameter binding, and there is a dead `PREPARE` block that is
overwritten before use. It worked and the result was verified, but do not reuse
that pattern on a workflow carrying live credentials.
