# ACTION-001 — Newspaper page OCR proof of concept

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The Jobdrive Newspaper Radar currently sources classified ads from
ads2publish.com through the `fetch_newspaper_ads` MCP tool. That source has
been proven, today, to serve stale or mismatched content: it claimed two
specific job ads ran in today's (17 Aug 2026) Amar Ujala Agra edition, and
neither appears anywhere in the real 16-page edition, while a real ad that
did run (Shanti Mangalick Hospital, page 5) never appeared on ads2publish at
all. That source cannot be trusted for freshness and the automated schedule
for it has been paused.

A replacement source has been found and confirmed live: an undocumented API
behind indupaper.com (a free epaper mirror) that returns real newspaper page
images. Confirmed today via direct test against n8n.amatec.in:

```
POST https://d1h47qec6ptx2j.cloudfront.net/amarujala/v1/download
Content-Type: application/json
Body: {"year":"2026","month":"08","day":"17","city":"agra-city","type":"main","page":"01"}

Response: {"status":"success","data":{"htmlContent":"<img src='data:image/jpg;base64,...'>","totalPage":16},"message":"OK"}
```

Confirmed working for pages 01, 02, 03 today, all returned real JPEGs
(600KB-1MB base64 each), `totalPage: 16` matches a real 16-page PDF edition
independently verified by hand. This endpoint is Amar Ujala only; other
papers on indupaper.com will need their own endpoints captured the same way
later, out of scope for this brief.

This gets image data, not text. Before any real pipeline gets built on top of
it, we need to know: can the VPS actually turn a real newspaper page image
into literal, trustworthy text? On 2026-08-11 a vision/summarizing model was
asked to read newspaper page images for this same project and it **fabricated
three ads with named organisations that did not exist**. That is the exact
failure this proof of concept exists to rule out. The OCR step must be a real
deterministic OCR engine, not an LLM reading the image and describing what it
thinks is there. Judgment about which ads qualify as leads happens later, in
a separate step, over the raw extracted text, not here.

## Step 1 — report only, no changes

1. What OCR tooling is already installed on the VPS or easily installable:
   Tesseract (and whether `hin` / Hindi language data is available, since
   most target papers are Hindi), or any other real OCR engine (Google Cloud
   Vision, AWS Textract, etc) already integrated somewhere in this repo or
   its infra.
2. Fetch ONE fresh sample page directly from the confirmed endpoint above
   (page "01", same params as shown) and save it as
   `jd-lead-newspaper/ocr-poc/sample-amarujala-agra-p01.jpg`. Do not commit
   yet, just confirm you can reach the endpoint from the VPS and that the
   saved file is a valid JPEG (report file size and image dimensions).
3. Whether the VPS has outbound access to fetch arbitrary HTTPS endpoints
   like the one above (some sandboxes restrict this; confirm it works here).

Report key names only where credentials are involved. Never print a value,
not even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Create `jd-lead-newspaper/ocr-poc/ocr_test.py`.

Requirements:

- Takes a path to a JPEG image, runs a real OCR engine against it (Tesseract
  with Hindi language data if that's what Step 1 found available), and
  writes the literal extracted text to a Markdown file next to it
  (`<name>.md`), one paragraph or line per detected text block, nothing
  invented, nothing summarized. If a region is illegible, note that rather
  than guessing.
- No LLM call anywhere in this script. This is a mechanical OCR pass only.
- Exit 0 on success, non-zero with a clear message if the image can't be
  read or OCR produces no text at all.
- Explicit non-goal: no classification, no filtering, no judgment about
  what's a job ad. Just raw text extraction.

Then run it once against the sample image from Step 1 and paste the real
output, including the full generated Markdown file content. Not a summary of
the output.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/ocr-poc/sample-amarujala-agra-p01.jpg`,
  `jd-lead-newspaper/ocr-poc/ocr_test.py`, and the generated `.md` output to
  `main` with a message saying what it does and why.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after the Step 3 output has been
verified independently by reading the committed files back from GitHub and
comparing the OCR text against an independent human transcription of the
same page (already on hand):

- Merge to `main`.
- Delete this brief from `actions/`.
- If anything learned here outlives the task, a trap, a corrected figure, a
  constraint discovered mid-run, move it into `jd-lead-newspaper/README.md`
  first.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the
  VPS.
- Do not touch `telecaller-app/`, `jd-lead-scrapping/`, or any existing file
  in `jd-lead-newspaper/` outside the new `ocr-poc/` folder.
- Do not touch the existing Newspaper Radar n8n workflows or the Lead
  Scraper MCP server. This is a parallel, separate proof of concept.
- Do not restart, stop or reconfigure any running service.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when `python3 jd-lead-newspaper/ocr-poc/ocr_test.py jd-lead-newspaper/ocr-poc/sample-amarujala-agra-p01.jpg` runs, produces a non-empty `.md` file containing real extracted text from the image (not placeholder or invented text), exits 0, and all three files are committed and pushed to `main`.