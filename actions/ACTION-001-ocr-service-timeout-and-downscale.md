# ACTION-001 — OCR service: raise timeout, downscale input, report timeouts distinctly

Owner: Anirban
Repo: anirban475/lead-manger
Target directory: `jd-lead-newspaper/ocr-service/`
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

We are about to run an 8-week OCR sweep over roughly 4,300 newspaper page images
to work out which weekday each paper runs its recruitment section. The output is
a map of "this paper carries appointment ads on this weekday". Every page that
fails is recorded as a page with no recruitment ads on it.

That is the problem. Right now a page that times out is indistinguishable from a
page that OCR'd cleanly and contained nothing. The service has a 60 second hard
Tesseract subprocess timeout, and Rajasthan Patrika page 2 hit it on every single
attempt across multiple passes. It is always the dense pages that time out, and
dense pages are exactly where classified ads live.

So the failure is not "some pages error". The failure is that the sweep produces
a confident, wrong map: a paper whose recruitment page is dense enough to time
out gets recorded as having no recruitment day at all, and we drop it from the
pipeline permanently on the strength of a bug.

Measured facts about the real input, captured 2026-08-18 from live endpoints:

- Times of India page image: 1,881,644 bytes, JPEG, 2748 x 4278
- Hindustan Times page image: 2,874,290 bytes, JPEG, 2163 x 3400
- Hindustan Times images are served with a `.webp` filename but the bytes are
  JPEG. `file` confirms this. Do not branch on file extension anywhere.

These are large. Tesseract time scales with pixel count, so downscaling before
OCR is the main lever on both the timeout and the total sweep wall-clock.

## Step 1 — report only, no changes

Read the current state and report:

1. The full contents of `jd-lead-newspaper/ocr-service/app.py`.
2. The full contents of `jd-lead-newspaper/ocr-service/ecosystem.config.js`.
3. The exact bind address and port the service binds in code, quoted as the
   literal line. The repo README says `172.21.0.1:5050` and we believe the code
   may say `127.0.0.1:5050`. Report what the code actually says. Do not change it.
4. What is currently listening on port 5050, from `ss -ltnp` or equivalent.
5. `tesseract --version` and `tesseract --list-langs`.
6. Whether Python Pillow is importable in the environment the service runs in.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify `jd-lead-newspaper/ocr-service/app.py` and
`jd-lead-newspaper/ocr-service/ecosystem.config.js`.

Requirements, each stated as something checkable:

1. **Configurable subprocess timeout.** The Tesseract subprocess timeout must be
   read from environment variable `OCR_TIMEOUT_SECONDS`, defaulting to `300`
   when unset. It must no longer be a hardcoded 60.

2. **Downscale before OCR.** Before invoking Tesseract, if the image's longest
   edge exceeds `OCR_MAX_EDGE_PX` (env var, default `2200`), resample the image
   down so its longest edge equals that value, preserving aspect ratio. Feed the
   downscaled image to Tesseract. Do not modify or write back the original.
   Detect the format by sniffing content, never by filename or extension.

3. **Timeouts must be distinguishable from empty results.** This is the whole
   point of the task. On a Tesseract timeout the response must carry
   `"status": "timeout"` and HTTP status `504`. A successful OCR that happens to
   find no text must carry `"status": "ok"` and HTTP `200` with an empty text
   field. A caller must never have to guess which happened.

4. **Report what was done.** Every successful response includes
   `original_size` as `[width, height]`, `ocr_size` as `[width, height]` after
   any downscale, and `duration_seconds` as a float.

5. **Worker count configurable.** In `ecosystem.config.js`, the Gunicorn worker
   count must come from environment variable `OCR_WORKERS`, defaulting to `4`
   instead of the current hardcoded 2.

6. **Explicit non-goals.** Do not change the bind address. Do not change the
   `lang` parameter handling. Do not add authentication. Do not add caching. Do
   not touch anything outside `jd-lead-newspaper/ocr-service/`.

Then test it, **on port 5051 only**, without touching the service running on
5050:

```
cd /root/projects/lead-manger/jd-lead-newspaper/ocr-service
curl -sS -o /tmp/ocr_test_toi.jpg "https://andre-toi-out.s3.ap-south-1.amazonaws.com/PublicationData/TOI/cap/2026/06/23/Page/23_06_2026_001_cap.jpg"
curl -sS -o /tmp/ocr_test_ht.webp "https://www.livehindustan.com/ep-img/prod/ht-epaper/2026/06/23/pages/HT_DELH/HT_DELH_FRONT_B1_P001_20260623_hr.webp"
OCR_TIMEOUT_SECONDS=300 OCR_MAX_EDGE_PX=2200 python3 app.py --port 5051 &
```

Then POST each of the two test images to `http://127.0.0.1:5051/ocr?lang=eng`
and paste the **real** response for each, not a summary. Then stop the port 5051
process.

Both must return `"status": "ok"`, a non-empty text field, an `ocr_size` whose
longest edge is 2200, and a `duration_seconds`. Report both durations, since
they set the budget for the 4,300-page sweep.

Also demonstrate the timeout path is real: re-run the TOI image once with
`OCR_TIMEOUT_SECONDS=1` and paste the response. It must be HTTP 504 with
`"status": "timeout"`, not an empty-text 200.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/ocr-service/app.py` and
  `jd-lead-newspaper/ocr-service/ecosystem.config.js` to `main`, with a message
  saying what changed and why.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 output is verified
independently.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- **Do not restart, stop, reload or reconfigure the OCR service running on port
  5050.** It stays up and untouched for the whole of this task. All testing
  happens on port 5051 and the test process is stopped afterwards. Deploying the
  change is a separate decision that Anirban makes, not part of this brief.
- Do not run `pm2 restart`, `pm2 reload`, `pm2 stop` or `pm2 delete` against
  anything.
- Do not edit any file under `jd-lead-newspaper/ocr-poc/` or
  `jd-lead-scrapping/`.
- Do not print environment variable values, tokens or credentials. Names only.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when all three of these hold and the change is pushed to `main`:

1. POSTing the TOI test image to the port 5051 instance with
   `OCR_TIMEOUT_SECONDS=300 OCR_MAX_EDGE_PX=2200` returns HTTP 200,
   `"status": "ok"`, non-empty text, and `ocr_size` with longest edge 2200.
2. The same POST with `OCR_TIMEOUT_SECONDS=1` returns HTTP 504 and
   `"status": "timeout"`.
3. `ss -ltnp` still shows the original service listening on 5050, unchanged and
   with the same PID as reported in Step 1.
