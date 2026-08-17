# Newspaper Radar source migration — endpoint capture, 2026-08-17

Continuation of the source migration (see HANDOVER-newspaper-radar-source-migration.md). Captured via indupaper.com, DevTools Network tab, same method as the original Amar Ujala contract.

## Confirmed working

### Rajasthan Patrika

```
POST https://d1h47qec6ptx2j.cloudfront.net/rjpatrika/v1/download?state=rajasthan&city=jaipur-city&year=2026&month=08&date=17
```

Params are in the query string, not a JSON body (differs from Amar Ujala's contract shape). Tested with state=rajasthan, city=jaipur-city, date=2026-08-17. Response rendered the full 28-page edition (masthead confirms: वर्ष 71, अंक 163, पृष्ठ 28, जयपुर, सोमवार, 17 अगस्त 2026). Verified page 2 also loads with **no second network call** — unlike Amar Ujala, this contract appears to return the whole edition in one request rather than one call per page. Front page content (Lalithaa Jewellery IPO ad, real market data) matches what a real edition would carry that day.

### Dainik Jagran

```
GET https://d1h47qec6ptx2j.cloudfront.net/dainikjagran/v1/download?citySlug=262-National&day=17&month=Aug&year=2026
```

Note the different shape again: GET not POST, `month` as three-letter name ("Aug") not zero-padded number, `citySlug` instead of separate state/city. Tested with citySlug=262-National (Delhi / National edition), 2026-08-17. Response rendered a real front page, 14 pages total, headline on the same Sonia Gandhi/Vande Mataram story referenced in the original OCR ground-truth check, which cross-confirms it's real content and not fabricated. This replaces the old dead endpoint (`d3f65smzvvdjuh.cloudfront.net`, DNS doesn't resolve) noted in the handover.

**Important finding: the "no shared pattern across papers" assumption in the handover doc is wrong for at least these two.** Amar Ujala, Rajasthan Patrika, and Dainik Jagran all resolve to the *same* CloudFront distribution (`d1h47qec6ptx2j.cloudfront.net`), just with a different path prefix per paper (`amarujala`, `rjpatrika`, `dainikjagran`) and a different param contract per paper (JSON body vs query string, POST vs GET, date format varies). Worth testing whether other Hindi dailies on indupaper.com also share this distribution before assuming each needs a fully separate capture.

## Confirmed broken (indupaper.com side, not just old-endpoint dead)

### Dainik Bhaskar

The page's own JS is broken as of 2026-08-17, unrelated to the old dead-endpoint list already in the handover. `dainik-bhaskar.js` is referenced in a commented-out `<script>` tag and now 404s. `window.onload` throws `ReferenceError: defaultDainikBhaskarOption is not defined`, so the state/city dropdowns never populate and the View button's onclick calls a function that doesn't exist. No network request fires on click — there is nothing to capture until indupaper.com fixes their own page. Recovered the CloudFront domain from a `<link rel="preconnect">` tag: `d39ihfvw4fm8k.cloudfront.net` — different distribution from the other three, so the shared-distribution shortcut above does not apply here. Endpoint path and payload shape remain unknown.

Also hit a transient "watch an ad to unlock 24hr access" interstitial gate on Rajasthan Patrika's page (not present on Dainik Jagran or Amar Ujala) that cleared after being triggered once. Worth expecting this gate on other papers too.

## Open items carried forward

- Dainik Bhaskar still needs a fresh capture once indupaper.com's own JS bug is fixed, or an alternative source.
- Worth testing 2-3 more Hindi dailies (e.g. Hindustan, Navbharat Times) to see if they also share `d1h47qec6ptx2j.cloudfront.net`, which would make bulk capture much faster than "one full DevTools session per paper."
