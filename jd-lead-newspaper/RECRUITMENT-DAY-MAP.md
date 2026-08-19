# Recruitment day map

Result of the calibration sweep, run 2026-08-18, **corrected 2026-08-19**.

## Correction notice, read this first

The first version of this document counted **matrimonial classifieds as
recruitment**. Matrimonial ads are extremely phone-dense and use the words
*working*, *salary*, *qualified*, *REQ*, *seeks* and *MNC*, so they passed a
filter built on keyword count plus contact density.

**623 of the 1,152 counted phone numbers, 54%, were matrimonial.** The
highest-scoring page in the whole project, Times of India Delhi 2026-08-02 page
14 with 242 phone numbers, is entirely matrimonial: "SM4 Sanadhya Gaur Brahmin
Boy 27, 176, BTech, wrkng in Japanese Automob. Comp., Good Salary",
"Alliance Invite".

Sunday carried nearly all of the contamination. Wednesday was clean. The
corrected numbers below are what should be acted on.

## Method

Two-pass OCR over real newspaper page images from indupaper.

- **Pass 1** OCRs a 2200px downscale of every page and counts recruitment
  keywords. Cheap, roughly 13s a page.
- **Pass 2** fires only when keyword count reaches 8, and OCRs the **original at
  full resolution** to count phone numbers and emails. Necessary because
  downscaling to 2200px destroys 86% of phone numbers.

A page counts as a recruitment page when it has 8+ keywords, 8+ phone numbers,
**and more recruitment markers than matrimonial markers**. That third condition
is the correction.

## Coverage

| Edition | Dates sampled | Pages OCR'd | Failures |
|---|---|---|---|
| Hindustan Times, Delhi | 17 | 417 | 0 |
| Times of India, Delhi | 16 | 424 | 0 |
| Mirror, Mumbai | 16 | 348 | 0 |
| Times of India, Ahmedabad | 16 | 295 | 0 |
| **Total** | **2026-08-01 to 2026-08-17** | **1,484** | **0** |

## The corrected answer: Sunday and Wednesday, closer than they looked

Genuine recruitment pages only, matrimonial excluded:

| Weekday | Recruitment pages | Phones | Was, before correction |
|---|---|---|---|
| **Sunday** | 6 | **254** | 877 |
| **Wednesday** | 7 | **150** | 150 |
| Tuesday | 3 | 88 | 88 |
| Saturday | 2 | 16 | 16 |
| Friday | 1 | 12 | 12 |
| Monday | 1 | 9 | 9 |
| Thursday | 0 | 0 | 0 |

Sunday's lead over Wednesday collapses from 5.8x to 1.7x once matrimonial ads
are removed. Wednesday's numbers did not move at all, because Wednesday carries
no matrimonial section.

**Sunday plus Wednesday is 404 of 529 genuine contacts, 76%.** Adding Tuesday
takes it to 93%. Thursday remains empty.

Note that Wednesday actually yields *more* recruitment pages than Sunday, 7
against 6. Sunday wins on volume per page, not frequency.

## Sector mix, and the ICP problem

Keyword counts across the top flagged pages:

| Sector | Mentions |
|---|---|
| Education (school, teacher, PGT, TGT, principal, CBSE, coaching) | 269 |
| Medical (hospital, nurse, GNM, MBBS, RMO, pharmacist) | 96 |
| Industrial (pharma, chemical, manufacturing, production, warehouse) | 32 |

The Jobdrive ICP is small pharma, chemical and manufacturing firms. Education is
already on the hard-drop list and coaching centres have their own reject reason.
**The qualified yield may therefore be far below the raw contact count**, and
that has to be measured before any of this is wired to the production leads
database. That measurement is ACTION-004.

## Genuine recruitment examples

Confirmed real ads with direct employer contacts:

- Pinegrove School, Subathu — Resident Medical Officer, MBBS/BAMS, salary
  stated, `office@pinegroveschool.com`
- A 50-bed hospital in Shakti Nagar, Delhi — GNM/B.Sc nursing staff, two mobiles
- N.R Jindal Public School, Uttam Nagar — Principal, 9871345048
- MBS College — lab assistants, librarian, sports coach, nurse

Note that all four are education or medical. That is the pattern, not a
coincidence.

## What this means for the schedule

Run **Sunday and Wednesday**. Consider Tuesday as a third day, since it now
out-yields Saturday, Friday and Monday combined. Thursday can be dropped
outright.

At Sunday plus Wednesday, roughly 200 pages a week for the current four
editions, about 11 minutes of OCR.

## Caveats

Two to three samples per weekday. Enough to act on, not enough to declare a
single-sample weekday truly empty.

Four English metro editions only. Hindi papers were deliberately deferred and
are likely to carry more of the Jobdrive ICP.

Contact counts are raw regex matches, not deduplicated or validated.
