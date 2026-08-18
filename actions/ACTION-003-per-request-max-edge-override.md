# ACTION-003 — Per-request max-edge override, and re-run pass 2

Owner: Anirban
Repo: anirban475/lead-manger
Files: `jd-lead-newspaper/ocr-service/app.py`, `jd-lead-newspaper/sweep/sweep.py`
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The sweep's whole design is two-pass. Pass 1 OCRs a 2200px downscale cheaply to
find recruitment pages by keyword. Pass 2 is supposed to OCR the **original at
full resolution** to extract phone numbers and emails, because downscaling
destroys them.

**Pass 2 is not running at full resolution.** It sends the original bytes to the
OCR service, but the service reads `OCR_MAX_EDGE_PX` from its own environment,
which pm2 sets to the default 2200. So the service downscales the image anyway
and pass 2 silently produces pass 1 quality.

Caught by checking the sweep against a page whose true values are known.
Times of India Delhi, 2026-08-12, page 10, a confirmed appointments page:

| source | phones | emails |
|---|---|---|
| direct Tesseract, full resolution 2748x4278 | **36** | **14** |
| calibration at 2200px | 5 | 2 |
| **what the sweep recorded** | **4** | **2** |

The sweep's numbers match the 2200px calibration, not the full-resolution truth.
Pass 2 is doing nothing that pass 1 did not already do, at roughly double the
cost.

This matters beyond one page. Contact density is the signal that separates a
real classifieds page from a keyword-rich false positive such as a tender notice
or an education feature. At 2200px that signal is 86% destroyed, so the sweep
cannot currently tell the two apart.

The keyword counts from pass 1 are unaffected and remain valid. Only phone and
email counts are wrong.

## Step 1 — report only, no changes

Report:

1. The current `process_and_downscale_image` and `ocr` functions from
   `jd-lead-newspaper/ocr-service/app.py`.
2. The pass 2 call site in `jd-lead-newspaper/sweep/sweep.py`, quoted.
3. `pm2 jlist` output for `ocr-service` showing which environment variables it
   was started with. Names and values for `OCR_*` only, no credentials.
4. How many rows currently satisfy `keyword_count >= 8` in
   `/root/newspaper_sweep/sweep.db`.

Stop after reporting. Do not write anything yet.

## Step 2 — build

### 2a. OCR service: accept a per-request override

In `app.py`, the `/ocr` endpoint must accept an optional `max_edge` query
parameter that overrides `OCR_MAX_EDGE_PX` for that request only.

- `?max_edge=2200` downscales to 2200 as now.
- `?max_edge=0` means **do not downscale at all**, pass the original bytes
  straight to Tesseract.
- Absent means fall back to the `OCR_MAX_EDGE_PX` environment default.
- A non-integer or negative value returns HTTP 400. Do not silently ignore it.

The response must keep reporting `original_size` and `ocr_size` so a caller can
always verify which resolution was actually used. This is the check that would
have caught the current bug, so it must stay accurate.

### 2b. Sweep: use it, and allow re-running pass 2

In `sweep.py`:

- Pass 1 calls the service with `max_edge=<--max-edge>` (default 2200).
- Pass 2 calls the service with `max_edge=0`.
- **Assert what you got.** After pass 2, compare the returned `ocr_size` against
  the returned `original_size`. If they differ, that page's `status` becomes
  `ocr_failed` with an error saying pass 2 was downscaled. A silent wrong number
  is worse than a recorded failure.
- Add a `--repass2` flag. When set, the runner does not scan new dates. It
  selects existing rows where `keyword_count >= --keyword-threshold`, re-runs
  pass 2 only on those at full resolution, and updates `phone_count`,
  `email_count`, `full_text` and `pass2_seconds` in place. It must not touch
  `keyword_count` or `ocr_chars`, which are already correct.

### Non-goals

Do not change pass 1 behaviour, the keyword list, the schema, the threshold
default, or the bind address. Do not add authentication or caching.

### Test, and paste real output

A full sweep is running right now under PID 245616 against the same database.
Do not stop it and do not delete the database.

Test the service on **port 5051 only**, leaving 5050 alone:

```
cd /root/projects/lead-manger/jd-lead-newspaper/ocr-service
curl -sS -o /tmp/fx.jpg "https://andre-toi-out.s3.ap-south-1.amazonaws.com/PublicationData/TOI/cap/2026/08/12/Page/12_08_2026_010_cap.jpg"
OCR_MAX_EDGE_PX=2200 python3 app.py --host 127.0.0.1 --port 5051 &
```

Then POST `/tmp/fx.jpg` three times and paste each real response's
`original_size`, `ocr_size`, `char_count` and a count of how many
`[6-9][0-9]{9}` matches the text contains:

1. `?lang=eng` with no `max_edge` — expect `ocr_size` longest edge 2200
2. `?lang=eng&max_edge=2200` — expect the same
3. `?lang=eng&max_edge=0` — expect `ocr_size` == `original_size` == [2748, 4278]
   and roughly **36** phone matches, not 4

Case 3 is the acceptance. If it does not return an order of magnitude more phone
numbers than case 1, the fix has not worked.

Also POST once with `?max_edge=abc` and confirm HTTP 400.

Then stop the port 5051 process.

## Step 3 — commit

Commit both files, push, report the hash and `git show --stat HEAD`.

Remember `.gitignore` line 31 is `*.py`, so you must `git add -f`. A plain
`git add` will silently commit nothing.

## Step 4 — deploy and re-run

Claude does this, not Antigravity.

## Rules for this task

- Work only inside `/root/projects/lead-manger`.
- Do not restart, stop or reconfigure the service on 5050, or any pm2 process.
- Do not stop the running sweep (PID 245616) or delete
  `/root/newspaper_sweep/sweep.db`.
- Do not edit `.gitignore`.
- One step per reply. Finish a step, report, and wait.

## Acceptance

`?max_edge=0` on the fixture returns `ocr_size == original_size == [2748, 4278]`
and roughly 36 phone-number matches, `?max_edge=abc` returns 400, the running
sweep and its database are untouched, and both files are pushed to `main`.
