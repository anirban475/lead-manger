# ACTION-003 — Test and expand region coverage per indupaper paper

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

`jd-lead-newspaper/indupaper-contracts.json` (committed, see commit `f218a40`)
gives 18 working paper contracts, each with a `regions_found` list. That list
is incomplete in two different ways and we don't yet know which:

1. Three papers (Hindustan Times, Hindustan, Kannada Prabha) explicitly load
   their region list from a separate endpoint (`/hindustantimes/v2/cities`,
   `/hindustan/v2/states`, `/kannadaprabha/v1/cities`) that was never actually
   queried, only noted as existing. The `regions_found` for these three is
   whatever happened to be visible elsewhere on the page, not the real list.
2. Several papers use opaque numeric region IDs instead of city slugs
   (Haribhoomi: 9, 12, 13, 14, 15, 16, 17, 18, 19, 36, 46, 47, 61, 65, 74 —
   note the gaps; Dainik Navajyoti: 1 through 40 with some gaps; Malayala
   Manorama: 1 through 21 with gaps; Inext: a scattered set 1-21). We do not
   know if these gaps are real (only those IDs are valid) or just gaps in
   what the HTML happened to expose. If the ID space is denser than what was
   scraped, we can manufacture full coverage by trying a range instead of
   depending on each page's dropdown.

Also, nobody has confirmed that changing the region parameter actually
changes the returned content. Every contract so far was tested with exactly
one region value. If a paper silently ignores the parameter and always
returns the same city's edition, that contract is not what it looks like.

This action answers both questions before we build anything that depends on
region coverage being real or complete.

## Step 1 — report only, no changes

1. Fetch the three known dynamic region-list endpoints and report their full
   raw response: `GET https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/cities`,
   `GET https://d1h47qec6ptx2j.cloudfront.net/hindustan/v2/states`,
   `GET https://d1h47qec6ptx2j.cloudfront.net/kannadaprabha/v1/cities`.
2. For each of Haribhoomi, Dainik Navajyoti, Malayala Manorama and Inext,
   test 5 region ID values NOT already in `regions_found` — pick values that
   fill a gap in the existing sequence (for example Haribhoomi has 9 and 12
   but not 10 or 11, try those). Report the HTTP status and whether each
   returns real content or an error/empty result.
3. For 4 other working papers of your choice (not already covered above),
   pick TWO different values from their existing `regions_found` (not the one
   already tested in the contracts file) and fetch both. Report whether the
   two responses actually differ — different city name in the content,
   different page count, different masthead — or whether they return
   identical content regardless of region.

This is read-only. No file writes, no commits. Report all of this and wait.

## Step 2 — build

Only after Step 1 is reviewed. Using what Step 1 found:

- For the three dynamic-endpoint papers, replace their `regions_found` with
  the real full list from the endpoint (value plus human-readable name where
  the response provides one).
- For the four numeric-ID papers, if the gap-filling test in Step 1 showed
  the ID space is denser than what was scraped, determine the real valid
  range or ruleset (for example "1 to 40, no gaps" or "these 15 values only,
  confirmed by testing the gaps and getting real 404s"). State the evidence
  either way, do not guess.
- For every one of the 18 working papers, confirm from Step 1's two-region
  test whether the region parameter is proven to change content. Add a field
  `region_param_verified: true/false` per paper.

Write `jd-lead-newspaper/indupaper-regions.json`: one object per paper with
`indupaper_slug`, `region_scheme` (one of `dynamic_lookup_endpoint`,
`fixed_set_from_html`, `sequential_ids`, `unknown`), `regions` (the expanded
list, each item `{ "value": "...", "name": "..." }` where a name is known),
and `region_param_verified`.

Run a validation pass and paste the real output, same discipline as
ACTION-002: every one of the 18 working papers gets an entry, nothing
fabricated, gaps reported as gaps rather than filled in with a guess.

## Step 3 — commit

Commit `jd-lead-newspaper/indupaper-regions.json` to `main`, push, report the
commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, after independent verification.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- One step per reply. Finish a step, report, and wait.
- Never fabricate a region value or a test result. A gap that is genuinely a
  404 is data, report it as such rather than smoothing it over.
- Rate limit yourself sensibly, this is still someone else's free service.

## Acceptance

Done when `jd-lead-newspaper/indupaper-regions.json` exists on `main` with an
entry for all 18 working papers, each with real evidence behind
`region_scheme` and `region_param_verified`, and the Step 2 reply shows real
validation output confirming that.
