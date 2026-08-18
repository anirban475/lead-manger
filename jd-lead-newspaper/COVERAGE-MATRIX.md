# Edition coverage matrix

Decision record for which city editions to scan. Measured 2026-08-18 against two
Sundays of live data.

## Available regions

### Times of India — 14, all verified live

`ahmedabad` `bangalore` `bhopal` `chandigarh` `chennai` `delhi` `goa`
`hyderabad` `jaipur` `kochi` `kolkata` `lucknow` `mumbai` `pune`

One entry per city, no supplements. Typical edition is 18 to 34 pages.

### Mirror — 3, all verified live

`bangalore` `mumbai` `pune`

Not Mumbai-only. Ahmedabad Mirror is a separate paper with its own endpoint and
no region parameter at all.

### Hindustan Times — 72 entries, but only 32 real places

| Category | Count |
|---|---|
| Supplements, not news editions | 27 |
| Edition entries | 45 |
| Distinct places behind them | 32 |

The 27 supplements are 17 `brunch-*` (lifestyle), 4 `school-*`, 3 `*-live`,
plus `showstopper`, `south-mumbai-cafe` and `mumbai-city-htc-mumb`. None will
carry appointment classifieds.

The 45 edition entries collapse to 32 places because HT lists both `delhi` and
`delhi-city`, `lucknow` and `lucknow-city`, and so on. It also lists `gurgaon`
and `gurugram` separately for what is one city.

Places: `amritsar` `bengaluru` `chandigarh` `delhi` `east-delhi` `east-up`
`gurgaon` `gurugram` `haryana` `jalandhar` `jammu` `lucknow` `ludhiana` `malwa`
`mumbai` `navi-mumbai` `noida` `north-delhi` `patiala` `patna` `powai-mumbai`
`pune` `punjab` `rajasthan` `ranchi` `south-delhi` `thane` `uttrakhand`
`varanasi` `west-delhi` `west-mumbai` `west-up`

## The measurement

For each city, fetch the edition, OCR every page at 2200px, flag pages with 8+
recruitment keywords, then OCR those at full resolution and collect the set of
phone numbers. Then compare the sets between cities.

### Sunday 2026-08-09

| City | Unique phones |
|---|---|
| mumbai | 189 |
| bangalore | 111 |
| pune | 110 |
| chennai | 104 |
| ahmedabad | 84 |
| hyderabad | 76 |
| delhi | 1 |

Heavy overlap. Mumbai and Pune shared 93 numbers, Mumbai and Bangalore 71,
Bangalore and Hyderabad 73. Union 353 against a raw sum of 675, so **48% of the
volume was duplication**. Greedy marginal gain suggested Mumbai plus Chennai
plus Bangalore captured 92% and that Hyderabad added nothing.

### Sunday 2026-08-02

| City | Unique phones |
|---|---|
| delhi | 275 |
| mumbai | 113 |
| bangalore | 42 |
| chennai | 5 |

Almost no overlap. The largest pair shared 3 numbers. Union 429 against a raw
sum of 435, so **1% duplication**.

## The finding: syndication is not stable

Two things swing violently week to week and neither is a fixed property of a
city.

**Which city is richest.** Delhi went from 1 phone to 275 across consecutive
Sundays. Chennai went from 104 to 5. Any ranking built on a single date is
noise.

**How much editions overlap.** Duplication was 48% one Sunday and 1% the next.
Some weeks Times of India runs a shared national classifieds package across
editions; other weeks each city runs its own.

This kills the obvious optimisation. There is no stable "best three cities" to
pick, because the week where a city looks redundant is not the week it is
carrying unique ads. Choosing a subset on one week's data would have dropped
Delhi, which two weeks in the sweep showed as the single highest-yielding
edition in the whole project (242 and 275 phones).

## Decision

**Scan every available edition, and deduplicate on the contact rather than on
the edition.**

Justified because the compute is close to free. The recruitment-day map already
cut the schedule to Sunday and Wednesday, so:

| Scope | Editions | Pages per week | OCR time per week |
|---|---|---|---|
| Current 4 | 4 | ~200 | ~11 min |
| All TOI + all Mirror | 17 | ~780 | ~42 min |
| Plus 8 distinct HT metros | 25 | ~1,180 | ~64 min |

At roughly 13 seconds a page across 4 workers, even the widest scope is about an
hour a week. Edition selection is not worth optimising against an hour of CPU
when the cost of guessing wrong is permanently missing the weeks a city carries
unique ads.

**Recommended scope:** all 14 TOI cities, all 3 Mirror cities, and HT restricted
to distinct metros only, skipping the `brunch-*`, `school-*` and `*-live`
supplements and the `-city` duplicates.

## Consequences

**Deduplication moves from nice-to-have to load-bearing.** With duplication
swinging between 1% and 48%, the lead pipeline has to dedup on the phone number
and email across editions and dates, not on page identity. This raises the
priority of the dedup and state-tracking work.

**Do not rank editions by a single sample.** Any future coverage decision needs
several weeks per city, and given the variance observed, probably a month.

**Archive gaps are real and silent.** On 2026-08-16 seven TOI cities returned
exactly 1 page while the same cities returned 18 to 34 pages on three other
dates. A single-page edition is an archive gap, not a thin paper. The runner
should flag any edition returning fewer than about 5 pages as suspect rather
than recording it as a genuine empty result.
