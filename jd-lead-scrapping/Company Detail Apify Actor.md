# System Instructions for TheCompanyCheck EPFO Scraper Actor

Use these instructions in Claude (as a Custom Instruction, System Prompt, or Project Knowledge file) to guide it on how to interact with and call the **TheCompanyCheck EPFO Scraper** Actor on Apify.

---

## Actor Description
The **TheCompanyCheck EPFO Scraper** searches for and scrapes Indian company profiles from `thecompanycheck.com`, retrieving precise EPFO employee headcounts, registered states, incorporation years, and financial status details.

- **Source**: `thecompanycheck`
- **Primary Use Case**: Determining company headcounts, verification of registration state, and financial/corporate status in India.
- **Fail-safe Fallback**: Automatically resolves unlisted brands (e.g., *Exemed*) by switching to `BRAND` search when standard `COMPANY` search yields no results.

---

## How to Call the Actor (API Call)

### Input JSON Structure
Provide the following JSON payload when starting a run:

```json
{
  "companyNames": ["Aneta Pharmaceuticals", "Exemed Pharmaceuticals"],
  "cins": ["L24231PN1981PLC024251"],
  "maxResults": 10,
  "maxConcurrency": 3,
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"],
    "apifyProxyCountry": "IN"
  }
}
```

### Input Fields Description:
- **`companyNames`** (array of strings, optional): Company names to search.
- **`cins`** (array of strings, optional): Precise Corporate Identification Numbers to scrape directly (bypassing search).
- **`maxResults`** (integer, optional): Maximum lookup records to process.
- **`maxConcurrency`** (integer, default 3): Concurrency limit (keep it polite to avoid geoblocking).
- **`proxyConfiguration`** (object): Apify residential proxy targeted to `IN` (India) to bypass geo-restrictions.

---

## Output Dataset Schema

Each scraped entity is pushed as a row in the Apify dataset with the following structure:

```json
{
  "query": "Aneta Pharmaceuticals",
  "matched": true,
  "lowConfidence": false,
  "matchConfidence": 1.0,
  "name": "Aneta Pharmaceuticals Private Limited",
  "cin": "U24230GJ2022PTC131644",
  "employees": 188,
  "employeesAsOf": "Feb 27, 2025",
  "activeEpfoEstablishments": 1,
  "employeeGrowthPct": 56.67,
  "revenuePerEmployee": "₹37.3 Lakh",
  "status": "Active",
  "registeredState": "Gujarat",
  "incorporationYear": 2022,
  "url": "https://www.thecompanycheck.com/company/aneta-pharmaceuticals-private-limited/U24230GJ2022PTC131644/",
  "source": "thecompanycheck",
  "scrapedAt": "2026-07-08T14:48:50.000Z"
}
```

### Output Fields Reference:
- **`query`**: The input string used for matching (company name or CIN).
- **`matched`**: `true` if matched legal entity is resolved, `false` if not found.
- **`lowConfidence`**: Flag set to `true` if match confidence ratio falls below `0.80`.
- **`matchConfidence`**: String similarity score (0 to 1) computed using token overlap + Jaro-Winkler metrics.
- **`name`**: Legal registered name.
- **`cin`**: Corporate Identity Number (CIN).
- **`employees`**: Scraped EPFO headcount (integer).
- **`employeesAsOf`**: Validity date for the employee headcount.
- **`activeEpfoEstablishments`**: Active EPFO registration offices count.
- **`employeeGrowthPct`**: Headcount growth rate as percentage.
- **`revenuePerEmployee`**: Revenue per worker string.
- **`status`**: Company status (e.g. `Active`, `Strike Off`).
- **`registeredState`**: State of ROC registration.
- **`incorporationYear`**: Year of incorporation.
- **`url`**: The profile page URL visited.

---

## Operational Guardrails & Guidelines

1. **Precision Matching**: If match confidence is low (< 0.80), the output row will still be written but marked with `lowConfidence: true`. Always check this flag to prevent silent data mismatches.
2. **Direct CIN URLs**: When querying a CIN directly, the crawler bypasses search and hits `/company/dummy-slug/{cin}/` directly. Note the trailing slash `/` is critical for listed/unlisted company pages to redirect correctly.
3. **Empty/Not Found Handling**: If no candidate matches, the actor writes a row with `matched: false`, `employees: null`, and a note explaining the failure mode. Do not assume any missing queries crashed the run.
