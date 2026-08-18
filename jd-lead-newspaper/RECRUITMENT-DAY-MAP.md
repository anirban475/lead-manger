# Recruitment day map

Result of the calibration sweep, run 2026-08-18. This is the answer to "which
weekday does each paper run its appointments section", and it is what the
production schedule should be built on.

## Method

Two-pass OCR over real newspaper page images from indupaper.

- **Pass 1** OCRs a 2200px downscale of every page and counts recruitment
  keywords. Cheap, roughly 13s a page.
- **Pass 2** fires only when keyword count reaches 8, and OCRs the **original at
  full resolution** to count phone numbers and emails. Necessary because
  downscaling to 2200px destroys 86% of phone numbers.

A page counts as a recruitment page when it has **8 or more keywords AND 8 or
more phone numbers**. Both conditions matter. Keywords alone produce constant
false positives, because ordinary news prose contains "required", "wanted" and
"candidate". Contact density alone would catch property and matrimonial
classifieds.

## Coverage

| Edition | Dates sampled | Pages OCR'd | Failures |
|---|---|---|---|
| Hindustan Times, Delhi | 17 | 417 | 0 |
| Times of India, Delhi | 16 | 424 | 0 |
| Mirror, Mumbai | 16 | 348 | 0 |
| Times of India, Ahmedabad | 16 | 295 | 0 |
| **Total** | **2026-08-01 to 2026-08-17** | **1,484** | **0** |

Two to three samples of each weekday per edition.

## The answer: Sunday, then Wednesday

Contacts recovered, aggregated across all four editions:

| Weekday | Recruitment pages | Phones | Emails |
|---|---|---|---|
| **Sunday** | **11** | **877** | **151** |
| **Wednesday** | **7** | **150** | **59** |
| Tuesday | 3 | 88 | 21 |
| Saturday | 2 | 16 | 15 |
| Friday | 1 | 12 | 3 |
| Monday | 1 | 9 | 3 |
| Thursday | 0 | 0 | 0 |

**Sunday alone carries 74% of every contact found. Sunday plus Wednesday carries
89%.** Thursday produced nothing at all across eight edition-days.

## Per edition

Reads as: editions containing a recruitment page / editions sampled.

| Edition | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Hindustan Times, Delhi | 0/3 | 1/2 | 1/2 | 0/2 | 0/2 | 1/3 | 1/3 |
| Times of India, Delhi | 1/3 | 1/2 | **2/2** | 0/2 | 0/2 | 0/2 | **2/3** |
| Times of India, Ahmedabad | 0/3 | 0/2 | 1/2 | 0/2 | 0/2 | 0/2 | **2/3** |
| Mirror, Mumbai | 0/3 | 0/2 | **2/2** | 0/2 | 1/2 | 1/2 | **3/3** |

Mirror Mumbai hit on every Sunday sampled. Times of India and Mirror both hit on
every Wednesday sampled.

## Highest yielding pages

| Edition | Date | Weekday | Page | Keywords | Phones | Emails |
|---|---|---|---|---|---|---|
| TOI Delhi | 2026-08-02 | Sunday | 14 | 11 | **242** | 29 |
| TOI Delhi | 2026-08-16 | Sunday | 12 | 8 | **177** | 18 |
| TOI Ahmedabad | 2026-08-09 | Sunday | 8 | 14 | 88 | 9 |
| TOI Delhi | 2026-08-16 | Sunday | 8 | 13 | 75 | 14 |
| TOI Ahmedabad | 2026-08-02 | Sunday | 6 | 10 | 70 | 8 |
| HT Delhi | 2026-08-02 | Sunday | 21 | 15 | 62 | 18 |
| HT Delhi | 2026-08-04 | Tuesday | 12 | 12 | 58 | 9 |
| TOI Delhi | 2026-08-05 | Wednesday | 8 | 12 | 41 | 13 |
| Mirror Mumbai | 2026-08-09 | Sunday | 20 | 33 | 35 | 18 |

Total across all flagged pages: **1,222 phone numbers and 507 email addresses**
from 17 days of four editions.

Page numbers cluster in the single digits to low twenties, but they move, so the
production run still has to scan the whole edition rather than jump to a fixed
page.

## What this means for the schedule

Run **Sunday and Wednesday only**. That is 2 days a week instead of 7, a 71% cut
in compute and bandwidth, for 89% of the available contacts. Thursday and Friday
can be dropped outright.

Estimated production load on the Sunday plus Wednesday schedule: roughly 8
edition-days a week at ~25 pages each, so about 200 pages a week. At the
measured 13s a page across 4 workers that is roughly 11 minutes a week.

## Caveats worth stating

Two to three samples per weekday. Strong enough to act on, not enough to call a
single-sample weekday like Monday truly empty. Extending the archive backfill
past 17 days would firm up the weak cells; the runner is resumable, so extending
costs nothing already spent.

The sweep covers four English metro editions. Hindi papers (Dainik Jagran,
Hindustan) were deliberately deferred and are likely to carry more of the
Jobdrive ICP: small pharma, chemical and manufacturing firms with thin HR. This
map should not be assumed to transfer to them.

Contact counts are raw regex matches, not deduplicated or validated. The 242
figure on TOI Delhi 2026-08-02 includes repeats within the page.
