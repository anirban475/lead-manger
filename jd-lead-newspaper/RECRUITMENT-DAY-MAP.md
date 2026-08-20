# Recruitment day map

Third revision, 2026-08-19. Each revision changed the answer, so the history
matters as much as the result.

| Revision | Metric used | Winner | Why it was wrong |
|---|---|---|---|
| v1 | Raw phone counts | Sunday, 5.8x ahead | 54% of those phones were matrimonial ads |
| v2 | Qualified leads per edition-day | Wednesday on rate, Sunday on volume | Schools were being dropped as coaching centres, business-email score was 4x too low |
| **v3, current** | Qualified leads, corrected ICP rules | **Wednesday on both** | — |

## The answer

Measured across 12 editions and 106 qualified leads:

| Weekday | Edition-days | Leads | ICP | Leads per edition-day |
|---|---|---|---|---|
| **Wednesday** | 16 | **52** | 17 | **3.25** |
| **Sunday** | 20 | 44 | 15 | 2.20 |
| Tuesday | 8 | 6 | 3 | 0.75 |
| Friday | 8 | 2 | 1 | 0.25 |
| Saturday | 9 | 2 | 1 | 0.22 |
| Monday | 12 | 0 | 0 | 0.00 |
| Thursday | 8 | 0 | 0 | 0.00 |

**Run Wednesday and Sunday.** Together they are 96 of 106 leads, 91%.

Wednesday now leads on both rate and absolute volume despite fewer edition-days
sampled. Sunday only ever looked dominant because matrimonial classifieds run on
Sundays and the first measurement counted their phone numbers as recruitment
contacts.

**Monday and Thursday are hard zeros** across 20 edition-days combined. Drop them.

Tuesday is a defensible third at 0.75 leads per edition-day, adding roughly 10%
for 50% more runtime. Friday and Saturday rest on two leads each, which is noise
rather than measurement.

## Method

Two-pass OCR over real page images.

- **Pass 1** OCRs a 2200px downscale and counts recruitment keywords, ~13s a page.
- **Pass 2** fires at 8+ keywords and OCRs the **original at full resolution**,
  because downscaling to 2200px destroys 86% of phone numbers.

A page yields leads only if its ads pass, in order: a hiring verb must be
present, then matrimonial and property classifiers must not fire, then the
sector and scoring gates.

## The three corrections that changed the numbers

**Matrimonial ads were counted as recruitment.** 623 of 1,152 phone numbers.
The highest-scoring page in the project, TOI Delhi 2026-08-02 page 14 with 242
phones, is entirely matrimonial: "SM4 Sanadhya Gaur Brahmin Boy 27, BTech, Good
Salary", "Alliance Invite".

**Every school and college was dropped as a coaching centre.** 24 ads, all
genuine schools and colleges. Anirban's rule: schools and colleges are valid
targets, only coaching centres are dropped. Hospitals are ICP too, since they
need educated staff, often have no HR function, and the screening load falls on
a doctor.

**The business-email bonus was +5 where this repo's own README specifies +20.**
Real employers with business domains were sitting at exactly 40 against a
50 threshold. A CA firm hiring ten audit assistants at `hr@yardiprabhu.com` was
being dropped as low score.

Together: survivors 31 to 68, ICP 7 to 25, hot tier 2 to 21, on identical pages.

## The guard that keeps it honest

Widening the sector rules created a new false positive: **clinics advertising
treatments and schools advertising admissions**, both of which carry the sector
noun and a phone number. Real cases found: ads for piles, psoriasis and
infertility treatment, and a college ad reading "required to submit semester fee
of Rs. 32200... Admission Helpline".

An ad only classifies as recruitment if it contains a **hiring verb**, checked
before the sector logic. Note that `required` must be excluded when followed by
`to `, or the admissions ad passes.

## Caveats

Two to three samples per weekday for most editions. Enough to act on, not enough
to call a single-sample weekday empty.

Contact counts are raw regex matches, not deduplicated or validated.

## The day map is TOI-shaped, and HT does not follow it (2026-08-20)

The v3 measurement above was taken across 12 editions dominated by Times of India
and Mirror. When Hindustan Times was restored to the sweep, its own history told a
different story. Pass-2 pages per day for `ht-delhi` across 18 consecutive days,
pass 2 being the gate that decides whether a phone number survives at all:

| Weekday | Edition-days | Pass-2 pages | Per day |
|---|---|---|---|
| Tuesday | 2 | 5 | **2.50** |
| Friday | 2 | 4 | **2.00** |
| Saturday | 3 | 5 | 1.67 |
| Sunday | 3 | 5 | 1.67 |
| Monday | 3 | 3 | 1.00 |
| Thursday | 2 | 1 | 0.50 |
| **Wednesday** | 3 | 2 | **0.67** |

HT Delhi's strongest single days were Tuesday 2026-08-11 at 33 keywords and Friday
2026-08-14 at 24. Wednesday is near its worst, and Wednesday is one of the two days
the cron runs. On Wednesday 2026-08-19 the whole 23-page HT Delhi edition peaked at
6 keywords, cleared no page for pass 2, and contributed nothing.

Seven editions sat in the same trap that day, maxing at 6 or 7 against a threshold
of 8: `ht-gurgaon`, `ht-lucknow`, `ht-noida`, `ht-varanasi`, `et-kolkata`,
`et-mumbai`, `mirror-bangalore`. A near-miss on the threshold is indistinguishable
in the data from a paper with no jobs in it.

**Do not conclude the new editions are weak.** That is one Wednesday, and the
coverage matrix already records that single-date rankings are noise, with Delhi
swinging from 1 phone to 275 across consecutive Sundays. The open question is
whether a per-paper day map beats one global schedule. Answering it needs several
weeks of per-edition weekday data, which the sweep is now collecting.
