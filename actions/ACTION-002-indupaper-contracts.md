# ACTION-002 — Capture working endpoint contract for every indupaper.com paper

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

We are replacing the Newspaper Radar's source entirely. The old 67-paper list
in the Playbook was scoped to ads2publish.com, which is being dropped because
it does not reliably mirror what actually ran in print (see
`HANDOVER-newspaper-radar-source-migration.md`). **That 67-list is no longer
the target.** The new target is whatever indupaper.com actually has working,
full stop, whether or not a given title happens to overlap with the old list.

`actions/ACTION-001-indupaper-catalog.md` (already run, see its thread) found
indupaper.com hosts 21 unique newspaper titles. Four already have a confirmed
contract from manual DevTools capture on 2026-08-17
(`jd-lead-newspaper/ocr-poc/source-contracts-2026-08-17.md`):

- `amar-ujala` — working, `POST https://d1h47qec6ptx2j.cloudfront.net/amarujala/v1/download`, JSON body `{"year","month","day","city","type","page"}`, one call per page number.
- `rajasthan-patrika` — working, `POST https://d1h47qec6ptx2j.cloudfront.net/rjpatrika/v1/download?state=...&city=...&year=...&month=...&date=...`, query string, one call returns the whole edition.
- `dainik-jagran` — working, `GET https://d1h47qec6ptx2j.cloudfront.net/dainikjagran/v1/download?citySlug=...&day=...&month=Aug&year=...`, query string, month is a three-letter name not a number.
- `dainik-bhaskar` — **broken on indupaper's own side**. `dainik-bhaskar.js` 404s, `window.onload` throws `defaultDainikBhaskarOption is not defined`, so the View button never fires a request. Recovered CloudFront domain only: `d39ihfvw4fm8k.cloudfront.net`, contract otherwise unknown. Do not spend more than one attempt re-checking this, just confirm it is still broken and move on.

This action captures the contract for the other 17: `times-of-india`,
`hindustan-times`, `the-hindu`, `economic-times`, `the-new-indian-express`,
`mirror`, `hindustan`, `haribhoomi`, `prabhat-khabar`, `maharashtra-times`,
`malayala-manorama`, `kannada-prabha`, `aaj-ka-anand`, `ahmedabad-mirror`,
`daily-excelsior`, `dainik-navajyoti`, `inext`.

## Method (already proven three times manually, replicate it server-side)

For a paper's page `https://www.indupaper.com/<slug>.html`:

1. Fetch the raw HTML with `curl`, not a browser.
2. Find the inline `<script>` block containing the view/download function
   (look for `async function view<PaperName>` or similar, and for
   `cloudfront.net`). Note: on at least one paper (Dainik Bhaskar) this logic
   lives in an external `<slug>.js` that may 404 — check for that first.
3. Extract: HTTP method (GET or POST), the full CloudFront URL, and whether
   parameters go in the query string or a JSON body, with their exact key
   names. Contracts differ per paper — do not assume any pattern from the
   three examples above carries over.
4. If the page has a state/city dropdown with options hardcoded in the HTML
   or inline JS, note the list of values found. If it is populated dynamically
   from an API call, just note that fact, do not chase the API in this task.
5. Fire ONE live test call: today's date (2026-08-17) and whichever
   region/city the page defaults to (or the first dropdown option if no
   default). Confirm HTTP 200 and that the response body looks like a real
   page (contains image data, or a page-count field, or similar), not an
   error page or empty payload.
6. If a paper's own page is broken (like Dainik Bhaskar), record status
   `broken` with the specific error, and move on. Do not debug indupaper's
   bugs for them.

## Step 1 — report only, no changes

Run the method above on 3 papers only: `times-of-india`, `hindustan-times`,
`the-hindu`. Report, for each: method, full URL, param style and keys, one
live test result (status code + a one-line description of what came back),
and any region/city values found. This is a check that the method above
actually works before running it across all 17.

Do not write any file, do not commit. Stop after reporting and wait.

## Step 2 — build

Only after Step 1 is reviewed and confirmed good: run the same method on the
remaining 14 papers (`economic-times`, `the-new-indian-express`, `mirror`,
`hindustan`, `haribhoomi`, `prabhat-khabar`, `maharashtra-times`,
`malayala-manorama`, `kannada-prabha`, `aaj-ka-anand`, `ahmedabad-mirror`,
`daily-excelsior`, `dainik-navajyoti`, `inext`).

Write ONE file, `jd-lead-newspaper/indupaper-contracts.json`, containing all
21 papers (the 4 already known, given above, plus the 17 captured here), one
JSON object per paper:

```json
{
  "paper_name": "Times of India",
  "indupaper_slug": "times-of-india",
  "page_url": "https://www.indupaper.com/times-of-india.html",
  "status": "working | broken | untested",
  "method": "GET | POST",
  "endpoint": "https://<cloudfront-domain>/<path>",
  "param_style": "query_string | json_body",
  "params_template": { "...": "..." },
  "regions_found": ["..."],
  "test": { "date_tested": "2026-08-17", "region_tested": "...", "http_status": 200, "notes": "..." }
}
```

Requirements:
- Every one of the 21 papers gets an entry. If a contract could not be
  captured, still include the entry with `status: "broken"` or `"untested"`
  and a `notes` field explaining why, rather than omitting it.
- Run a validation pass (a short script is fine) that checks every object has
  all the fields above, and paste the real output of that check, not a
  summary.
- Non-goal: do not attempt to enumerate every region/city for every paper.
  `regions_found` is whatever was visible on the page for free, not a target
  to chase down.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/indupaper-contracts.json` to `main` with a
  message describing what it is.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, after independently verifying Step 3.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not restart, stop or reconfigure any service.
- One step per reply. Finish a step, report, and wait.
- Never fabricate a contract or a test result. If a paper cannot be captured,
  say so plainly rather than guessing a plausible-looking URL.

## Acceptance

Done when `jd-lead-newspaper/indupaper-contracts.json` exists on `main`,
contains exactly 21 entries matching the schema above, and the Step 2 reply
shows real validation output confirming that.
