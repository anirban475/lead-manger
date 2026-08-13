# `leads_park` — the park store

Separate database on `shared-postgres`. One table, `newspaper_ad_raw`.
Created 2026-08-13 by `001_create_leads_park.sql`.

## Why it exists

The radar reads roughly 650 classified ads a morning and keeps about 50. The
rest were discarded in memory and never written anywhere. Ads2Publish is a
rolling window, so a discarded ad cannot be fetched again, ever.

Two failures made this urgent.

**Roughly 6,900 records already gone.** Counted from `radar_runs` on 2026-08-12,
across six runs: 9,415 pulled, 276 saved. The scoring rules are actively being
revised, so ads rejected under today's rules may qualify under next month's.
There was no way to re-score history because history was not kept.

**The counting did not reconcile.** On 2026-08-03 the run logged 1,988 pulled,
37 saved and 61 dropped, leaving **1,890 records unaccounted for**. `dropped`
was being derived as an arithmetic residual rather than counted. This is the
same failure mode as the invented "331 park ads" figure in trap 4 of the main
README. Once every ad has a row, the drop count becomes
`SELECT count(*) WHERE outcome = 'rejected'` and cannot be invented.

## Why raw ads and not parked lead rows

Storing the parser's output for rejects would freeze today's parser bugs
permanently. Two were known at build time:

1. The ad body is discarded, and **on this source the classified IS the job
   description**. Employers advertising here rarely hold a separate JD document,
   so without `ad_text` there is nothing to screen a forwarded resume against.
2. `roles_count` disagreed with `array_length(role_titles, 1)` on 14 of 80
   emailable newspaper leads, about 17%.

Storing the raw ad means both the parse and the score can be redone later.
Storing a parsed row means only the score can.

## Schema notes

Two check constraints carry weight and were tested on live input before merge:

- `outcome_chk` limits `outcome` to `saved`, `rejected` or `park`.
- `reject_reason_required` makes `reject_reason` mandatory whenever
  `outcome = 'rejected'`. Without it the table becomes a landfill instead of
  something you can query for why viable leads are being dropped.

`company_key` links back to `leads.leads` for rows that became leads. There is
no foreign key, because the two live in different databases.

## What is NOT done yet

**Nothing writes to this table.** It is empty by design.

Populating it means editing n8n workflow `aeWlxXTWGRHyGehZ`, and per trap 2 in
the main README the n8n API strips credentials from that workflow. That edit is
UI or targeted database update, by hand, never a full-replace write.

**No `postgres_fdw` link back to `leads`.** Cross-database joins are therefore
not possible from SQL. A foreign server needs a stored password, so it was left
out deliberately. Wire it by hand if ad-hoc analysis across both ever justifies
it.

## Retention

Roughly 1 GB a year at current volume, so no pressure. Worth setting a rule
before it becomes someone's problem rather than after.

## Infrastructure note found during this build

`docker exec shared-postgres psql -U admin -c "CREATE DATABASE ..."` emits:

```
WARNING: database "admin" has a collation version mismatch
DETAIL:  The database was created using collation version 2.41,
         but the operating system provides version 2.36.
```

Pre-existing and unrelated to this table, but a collation mismatch can corrupt
text indexes. Worth resolving on the `admin` database separately.
