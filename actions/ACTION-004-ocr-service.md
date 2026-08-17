# ACTION-004 — Standing Tesseract OCR HTTP service

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The Newspaper Radar pilot needs to turn indupaper.com page images into text
without routing every scheduled run through this Slack approval loop, and
without adding an FTP hop between fetch and OCR. The fix is a small standing
HTTP service on the VPS that wraps Tesseract (already proven working in
`jd-lead-newspaper/ocr-poc/ocr_test.py`, commit `1baf637`) so n8n's HTTP node
can call it directly and get text back in the same run. This brief builds that
service once. It is not meant to be re-dispatched per newspaper-radar run.

## Step 1 — report only, no changes

Read the current state and report:

1. Is `tesseract` already installed on this VPS (the binary the ocr-poc script
   already calls), and which language packs are present (need at minimum
   `hin` and `eng`)?
2. Is a Python web framework available (Flask or FastAPI), or does something
   else need installing?
3. What is this VPS's network relationship to `n8n.amatec.in` — same host, or
   a separate machine reachable over the private network? This decides
   whether the OCR service should bind to localhost only or a private
   interface.
4. Is there an existing process manager on this VPS for long-running services
   (systemd, pm2, supervisor, or something else), so the new service follows
   the same pattern as whatever else is already running here?
5. Are there any ports already in use that need avoiding?

Report key names only where credentials are involved. Never print a value,
not even partially. Stop after reporting. Do not write anything yet.

## Step 2 — build

Create `jd-lead-newspaper/ocr-service/` containing:

- A minimal HTTP service (`app.py` or equivalent) exposing `POST /ocr`. Input
  is a single image (multipart file upload or base64 in a JSON body, your
  choice, but document which in the file). Optional `lang` param, default
  `hin+eng`. It runs Tesseract against the image and returns JSON:
  `{"text": "...", "char_count": N}` on success.
- A process manager unit (systemd service file, or equivalent for whatever
  Step 1 found already in use) so the service survives the current SSH
  session ending and restarts if the VPS reboots. Commit this unit file
  alongside the code.

Requirements, each one checkable:

- A bad or corrupt image returns HTTP 400 with a JSON error field, not a
  crash and not a stack trace in the response body.
- A successful OCR call on a typical single newspaper page image completes
  in under 15 seconds.
- The service binds to localhost or the private interface only, per what
  Step 1 found about the VPS/n8n relationship. Do **not** bind to `0.0.0.0`
  or expose the port to the public internet. If the only way to reach it from
  n8n requires public exposure, stop and report that instead of opening it.
- No authentication needed for the pilot, this is an internal-only endpoint.
- One image per request is enough. No batch endpoint needed.
- Never log or return anything beyond the OCR text and the error field. No
  filesystem paths, no request internals, no secrets.

Then run it once for real: start the service, `curl -X POST` the running
local endpoint with the actual sample image already in this repo,
`jd-lead-newspaper/ocr-poc/sample-amarujala-agra-p01.jpg`, and paste the real
JSON response. Not a summary of the response.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/ocr-service/` to `main` with a message saying
  what it does and why.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after the Step 3 output has been
verified independently:

- Merge to `main`.
- Delete this brief from `actions/`.
- If anything learned here outlives the task, for example the true
  relationship between this VPS and n8n, or which process manager is
  standard here, move it into the repo README or the relevant Outline doc
  before deleting the brief.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the
  VPS.
- Do not restart, stop or reconfigure any other running service on this box.
- Do not expose the new service beyond localhost or the private interface
  without stopping to ask first.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when the OCR service is running as a standing process (survives an SSH
disconnect and VPS reboot), `curl -X POST .../ocr` against the real sample
image in this repo returns HTTP 200 with real extracted text in the JSON
body, the code and unit file are pushed to `main`, and the commit hash is
reported.
