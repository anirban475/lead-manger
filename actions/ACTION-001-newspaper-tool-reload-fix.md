# ACTION-001 — add_newspaper_mcp_tool.py: fix the silent reload failure

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Fixes: issue #1
Regressed in: commit `2b18006`

## Why this exists

`jd-lead-newspaper/add_newspaper_mcp_tool.py` writes the new `fetch_newspaper_ads`
node straight into the n8n Postgres tables, then tries to make n8n pick the change
up by calling the n8n REST API deactivate/activate endpoints.

That reload call cannot run. The file imports `sys, argparse, json, subprocess, uuid`
and nothing else, but the reload block calls `urllib.request.Request(...)` and
`urllib.request.urlopen(...)`. Python raises `NameError: name 'urllib' is not defined`
on the first call. The `except Exception: continue` immediately inside the loop
swallows it, once per API key, and then the loop ends. No warning is printed, the
outer `except` never fires, and the script exits 0.

Commit `2b18006` also deleted the previous DB-level active-flag toggle, so there is
now no fallback at all.

The visible result: the script says `[SUCCESS] Database updated successfully` and
exits 0, while the running n8n process still has the old workflow in memory and the
new tool node is not callable. Every acceptance signal says pass and the thing the
script exists to do did not happen.

Note on the fallback, because this is the part that is easy to get wrong: flipping
`workflow_entity.active` in Postgres does **not** reload n8n's in-memory workflow.
It is a weak fallback, not an equivalent one. It must never be reported as a
successful reload.

## Step 1 — report only, no changes

Read and report, no edits:

1. The exact import block at the top of `jd-lead-newspaper/add_newspaper_mcp_tool.py`.
2. The full reload block at the bottom of `main()`, quoted as it stands today.
3. Run `cd /root/projects/lead-manger && python3 -m pyflakes jd-lead-newspaper/add_newspaper_mcp_tool.py; echo EXIT=$?`
   and paste the real output and exit code. If pyflakes is not installed, install it
   with pip into the current environment and say so.
4. Confirm whether `psql` inside the `shared-postgres` container supports
   `-v name=value` plus `:'name'` literal interpolation. Report the psql version.

Report key names only where credentials are involved. Never print an API key value,
not even partially, not even masked. Do not paste the output of any query that
selects from `user_api_keys`.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify `jd-lead-newspaper/add_newspaper_mcp_tool.py` only.

Requirements:

- Add `import urllib.request` and `import urllib.error` to the import block.
- Extract the reload into a module-level function
  `reload_workflow_via_api(workflow_id) -> bool`. It returns `True` only when both
  the deactivate and the activate call returned a 2xx. It returns `False` otherwise.
- Inside that function, catch `urllib.error.HTTPError`, `urllib.error.URLError` and
  `OSError` per key, and print the status code or reason to stderr for each failed
  key. Do not use a bare `except Exception` anywhere in the reload path. A programming
  error must surface, not be swallowed.
- Print the number of API keys read from `user_api_keys`. Never print a key value or
  any prefix of one.
- Add a module-level function `reload_workflow_via_db(workflow_id) -> bool` that
  restores the old two-statement `active = false` then `active = true` toggle. It is
  only called when `reload_workflow_via_api` returned `False`.
- When the DB fallback is used, print to stderr, exactly this shape:
  `[RELOAD DEGRADED] REST reload failed. Toggled workflow_entity.active in Postgres, which does NOT reload n8n in-memory. Reload the workflow in the n8n UI before using the new node.`
- Exit code contract for the script:
  - `0` — DB write succeeded and `reload_workflow_via_api` returned `True`.
  - `2` — DB write succeeded, REST reload failed, fallback ran. Warning printed.
  - `1` — DB write failed, or the pre-flight checks already in the file failed.
  - `--dry-run` keeps its current behaviour and exits `0`.
- Replace the f-string SQL in the main DB write. Pass `nodes_json` and
  `connections_json` as psql variables through the argument list, and reference them
  in the SQL as `:'nodes'` and `:'conns'` with an explicit `::json` cast. No manual
  `.replace("'", "''")` quoting is to remain in the file.
- Non-goals: do not change the node definition, the connection definition, the
  credential-count guard, the backup step, the workflow ID, or the webhook URL.

Then run all three of these, in `/root/projects/lead-manger`, and paste the real
output and exit code of each. Not a summary of the output.

```
python3 -m pyflakes jd-lead-newspaper/add_newspaper_mcp_tool.py; echo EXIT=$?

git show 2b18006:jd-lead-newspaper/add_newspaper_mcp_tool.py > /tmp/before.py \
  && python3 -m pyflakes /tmp/before.py; echo EXIT=$?

python3 -c "import sys; sys.path.insert(0,'jd-lead-newspaper'); import add_newspaper_mcp_tool as m; print('RESULT:', m.reload_workflow_via_api('NO-SUCH-WORKFLOW-000'))"; echo EXIT=$?
```

The second command is the before/after proof. It must show the `undefined name 'urllib'`
lines that the current file produces and the first must not.

The third must print a real per-key HTTP or URL error and `RESULT: False`, and must
exit `0`. It must not raise `NameError`.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/add_newspaper_mcp_tool.py` on `main` with a message
  naming issue #1 and saying what broke and what now happens instead.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 has been verified
independently on GitHub:

- Confirm merged to `main`.
- Delete this brief from `actions/`.
- Move the in-memory-reload trap into `README.md` before deleting, since it outlives
  this task.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Edit only `jd-lead-newspaper/add_newspaper_mcp_tool.py`. Do not touch
  `jd-lead-scrapping/`, `telecaller-app/`, or anything under `actions/`.
- Do not restart, stop or reconfigure `n8n`, `shared-postgres`, or any docker container.
- Do not run this script without `--dry-run` against the live workflow
  `zUbadDjZ9PfMR8av`. No live DB write and no live activate/deactivate of that
  workflow in this task. The bogus workflow ID in the Step 2 test is deliberate.
- Never print an API key, a password, or the contents of any `.env`. Key names and
  counts only.
- One step per reply. Finish a step, report the real output, and wait.

## Acceptance

Done when, in `/root/projects/lead-manger` on `main`:

1. `python3 -m pyflakes jd-lead-newspaper/add_newspaper_mcp_tool.py` prints nothing
   and exits `0`, while the same command against `git show 2b18006:` of the file
   prints `undefined name 'urllib'`.
2. `python3 -c "...reload_workflow_via_api('NO-SUCH-WORKFLOW-000')"` prints a real
   connection or HTTP error and `RESULT: False`, and exits `0`.
3. `python3 jd-lead-newspaper/add_newspaper_mcp_tool.py --dry-run` prints the node and
   connection counts and exits `0`, with no database write.
4. No `except Exception` remains in the reload path, and no `.replace("'", "''")`
   remains in the file.
5. The change is pushed to `main`.
