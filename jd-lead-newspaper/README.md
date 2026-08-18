# Newspaper Radar — Jobdrive

A sweep of Indian newspaper classified recruitment ads. Newspaper job ads carry
what job boards strip out: the employer's own phone and email, printed so
candidates can apply direct.

## Source status

**Current source: indupaper.com, via OCR of real newspaper page images.**

**Ads2Publish is removed as a source (decision 2026-08-18).** It was a booking
agency's own published-ad archive, so it only ever showed ads placed through
that agency, never full daily editions. Its n8n workflow `aeWlxXTWGRHyGehZ` and
the Outline "Newspaper Radar Playbook" doc still exist as historical reference.
Do not re-enable it. Its lead-scoring and gating logic is still the pattern to
adapt; its source is not.

## Verified endpoint contracts

All manifest endpoints live on `https://d1h47qec6ptx2j.cloudfront.net`. They
return JSON: `{status, data: {htmlContent, totalPage}, message}` where
`htmlContent` is a string of `<div><img src="..."/></div>` blocks.

| Edition | Manifest request |
|---|---|
| Hindustan Times, Delhi | `/hindustantimes/v2/download?citySlug=delhi&editionDate=YYYY-MM-DD` |
| Times of India, Delhi | `/toi/v2/download?citySlug=delhi&day=DD&month=MM&year=YYYY` |
| Times of India, Ahmedabad | `/toi/v2/download?citySlug=ahmedabad&day=DD&month=MM&year=YYYY` |
| Mirror, Mumbai | `/mirror/v2/download?citySlug=mumbai&day=DD&month=MM&year=YYYY` |

Note that HT takes a single `editionDate` in `YYYY-MM-DD`, while TOI and Mirror
take three separate zero-padded `day`, `month`, `year` params. Other papers in
`indupaper-contracts.json` differ again, including case-sensitive variants
(`editionid` vs `editionId`) and a three-letter month name for Dainik Jagran.

Image hosts, parsed out of `htmlContent`:

- HT: `www.livehindustan.com/ep-img/prod/ht-epaper/YYYY/MM/DD/pages/HT_DELH/HT_DELH_<SECTION>_B1_P0NN_YYYYMMDD_hr.webp`
- TOI and Mirror share `andre-toi-out.s3.ap-south-1.amazonaws.com/PublicationData/<TOI|Mirror>/<EDITION>/YYYY/MM/DD/Page/DD_MM_YYYY_NNN_<EDITION>.jpg`

### Verified 2026-08-18

**Back-dating works.** Tested HT and TOI at 8 weeks back (2026-06-23), TOI at
2026-01-15 (32 pages) and at 2025-08-18. All returned real editions. The 2025
date returned only 8 pages, so older archives may thin out, but two months back
is comfortably inside the healthy zone. This is what makes an archive backfill
possible instead of waiting a week for live data.

**No Referer header is required.** Bare `curl` with no headers returns the
image: TOI 200 / 1,881,644 bytes, HT 200 / 2,874,290 bytes. Adding
`Referer: https://www.indupaper.com/` produced a byte-identical response.

## Traps

**1. `totalPage` is not a page count.** Mirror Mumbai reports `totalPage: 120`
while returning 20 images numbered 101 to 120. It is the highest page index.
Count the `<img>` tags instead, always.

**2. HT images are named `.webp` but contain JPEG bytes.** `file` confirms it.
Never branch on the filename or extension; sniff the content.

**3. The edition code varies by city and appears twice in every image URL.**
TOI Delhi is `cap`, TOI Ahmedabad is `toiac`, Mirror Mumbai is `vkmmir`. Parse
it from the manifest, never hardcode it.

**4. Page counts swing wildly by day.** TOI Delhi returned 14, 22, 32 and 8
pages across four sampled dates. Size every run from its own manifest.

**5. Ahmedabad Mirror inlines base64 instead of returning URLs.** It serves
`data:image/jpeg;base64,...` directly in `htmlContent`, one page per call, 20
calls per day, and takes no region parameter at all. It was dropped in favour
of TOI Ahmedabad, which covers the same city at one call per day on code that
already exists.

**6. There is an ad-gate interstitial on some papers.** A "watch an ad to
unlock 24hr access" gate was seen once on Rajasthan Patrika and cleared after
being triggered once. Expect it elsewhere.

**7. Never put a summarising model in the fetch path.** WebFetch silently
dropped ads on the old source: Deccan Chronicle jumped 2 to 4, Namasthe
Telangana 4 to 7, Kannada Prabha skipped 4. Fetch raw bytes.

**8. A vision agent fabricated three job ads that did not exist** when asked to
find them in publisher e-papers on 2026-08-11. OCR is deterministic; a model
reading a page is not. If a vision pass is ever added, it needs a fixture to
be measured against.

## OCR service

`ocr-service/` runs Gunicorn under pm2, bound to `172.21.0.1:5050` (the
`amatec-net` Docker bridge gateway). `app.py` also defaults `HOST` to that
address, but Gunicorn's `--bind` in `ecosystem.config.js` is what actually
takes effect.

Configuration, all environment variables with defaults:

| Variable | Default | What it does |
|---|---|---|
| `OCR_TIMEOUT_SECONDS` | 300 | Tesseract subprocess timeout |
| `OCR_WORKER_TIMEOUT` | 360 | Gunicorn worker timeout, must stay above the above |
| `OCR_WORKERS` | 4 | Gunicorn worker count |
| `OCR_MAX_EDGE_PX` | 2200 | Longest edge before downscaling |

**Why both timeouts matter.** Until 2026-08-18 the service had two stacked 60
second ceilings: Tesseract's subprocess timeout and Gunicorn's `--timeout 60`.
Raising only one achieves nothing, because Gunicorn kills the worker first and
the connection drops abruptly rather than returning a response. That is the
leading explanation for the n8n "connection was aborted, perhaps the server is
offline" error seen during long sequential runs.

**A timeout must never look like an empty page.** The service previously
returned HTTP 400 with `{"error": "OCR processing timed out"}`, the same shape
as a corrupt-image error. In a sweep whose entire output is "which pages carry
recruitment ads", a page that fails is otherwise recorded as a page with
nothing on it, and the densest pages are exactly the ones that both time out
and carry classifieds. It now returns HTTP 504 with `"status": "timeout"`,
distinct from a successful `"status": "ok"` with empty text.

### Measured OCR timings

Live Times of India Delhi pages, full resolution, on the VPS:

| Page | Image | Seconds | Chars |
|---|---|---|---|
| 9 | 1.67 MB | 52 | 15,788 |
| 10 | 2.03 MB | 86 | 27,477 |
| 12 | 1.89 MB | 89 | 24,311 |
| 16 | 2.19 MB | 88 | 37,630 |

Four pages in a single 32-page edition exceeded the old 60 second ceiling.
Page 10 is the appointments page. Under the previous configuration the sweep
would have recorded the one page that mattered as containing nothing.

Downscaled to 2200px longest edge, the same class of page OCRs in roughly 24
seconds and still yields 20,110 characters, so the text loss is negligible and
the speedup is large.

## Detection fixture

**Times of India, Delhi, Wednesday 2026-08-12, page 10.**

This is the first confirmed English recruitment page in the project. It carries
37 phone numbers and 14 email addresses, against a typical news page of 0 to 5
phones. Real ads found on it include:

- Pinegrove School, Subathu, H.P. — Resident Medical Officer, MBBS/BAMS, salary
  stated, applications to `office@pinegroveschool.com`
- A 50-bed hospital in Shakti Nagar, Delhi — GNM/B.Sc nursing staff, two mobile
  numbers printed
- Indian Buildings Congress — Executive Director on contract

Fetch it at
`https://andre-toi-out.s3.ap-south-1.amazonaws.com/PublicationData/TOI/cap/2026/08/12/Page/12_08_2026_010_cap.jpg`

Before this, the only confirmed ad anywhere in the project was Hindi (Shanti
Mangalick Hospital, Amar Ujala Agra, 2026-08-17 page 7), which could not
validate an English pipeline.

**Phone and email density beats keyword matching for finding the section.** A
broad keyword scan flagged 7 of the first 9 pages, all false positives, because
ordinary news prose contains "required", "wanted" and "candidate". One page
matched "OUR RECRUITMENT PARTNERS" and turned out to be a college advertising
its placement partners. Contact-detail density found the real page cleanly on
the first pass.

## Decisions worth not relitigating

**Business email outweighs every overload signal combined**, +20 against a +15
cap. Overload measures hiring pain, a business domain measures ability to pay,
and the second decides whether a lead is worth anyone's time. A firm still
applying through Gmail is usually too small to buy however desperate one ad
looks.

**Never filter on the company's home country.** The Naukri and LinkedIn radars
are India-only because a job board's location filter reflects where a company
operates. A newspaper ad is different: paying for a classified in an Indian
paper only makes sense if you are hiring in that paper's circulation area. The
ad placement is the proof and it beats the registered address.

**Callability is enforced through `score`, not a new field.** The telecaller
cockpit sorts by `score DESC` and caps at 200 rows, so score already is the
mechanism. Park leads are clamped to 25 and sink below the cut rather than
being withheld.

**Warm only, no hot tier, no recurrence mechanism.** There is no `applyCount`
equivalent in a newspaper ad. Leads go straight to contact rather than ripening.

## n8n hazards

**`update_workflow` strips credentials.** The lead-scraper MCP workflow serves
12 tools, ten of which carry credentials, and n8n's own
`get_workflow_details` returns those nodes with no credential IDs. Any
full-replace write built from that output silently removes authentication from
ten working tools. Edit in the UI or by targeted database update, never by
re-emitting the workflow.

**A raw `active` column flip does not reload n8n.** Setting
`workflow_entity.active` false then true in Postgres does not touch n8n's
in-memory activation manager. Use `POST /api/v1/workflows/{id}/deactivate` then
`/activate`, which take no request body and so cannot strip anything. Exit code
`2` from the helper scripts means the database write succeeded but n8n's memory
is stale.

**Counting rules.** Derive every aggregate from a list, never report a bucket as
a residual, and assert the header equals the sum before writing. The first
production run reported 58 saves and 640 ads while actually making 68 saves and
fetching 614, and its "331 park ads" was computed as total minus everything else
so the breakdown would balance. No park tally was ever made.

## Key IDs

| Thing | Where |
|---|---|
| n8n pilot workflow, indupaper | `k5ZrGIYFa9n2tyNa`, inactive, no cron yet |
| n8n workflow, Ads2Publish, deprecated | `aeWlxXTWGRHyGehZ` |
| Lead-scraper MCP workflow | `zUbadDjZ9PfMR8av` |
| CTO log | Outline "Amatec System Map", `f106c70a-6126-451c-92f4-fe3028a84984` |
| Old source playbook, reference only | Outline "Newspaper Radar Playbook", `45d91272-fb73-4938-b5d1-32be4ebf6894` |

## Environment gotchas

- The SSH exec tool has a hard 45 second timeout and kills the underlying shell.
  Launch long work with `nohup ... & disown`, then poll separately.
- SSH exec caps commands at 1000 characters. Split long heredocs across several
  `cat >>` calls.
- The sandbox cannot reach the S3 image host (`403 from proxy after CONNECT`).
  Download page images on the VPS, which has open egress.
- Tesseract on the VPS is 5.3.4 with `eng`, `hin` and `osd` only.
