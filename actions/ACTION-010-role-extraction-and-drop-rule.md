# ACTION-010 — Fix role extraction, then drop ads with no role

Owner: Anirban
Repo: anirban475/lead-manger
File: `jd-lead-newspaper/sweep/extract.py`
Working copy on VPS: `/root/projects/lead-manger`

**Check you are on `main` before committing.** A parallel session left the shared
working copy on a feature branch once already.

## Why this exists

Anirban's rule: an ad without a job role should be dropped, because a telecaller
cannot pitch against an unknown role.

The rule is right. Applying it today would be wrong, because **the roles are
there and the parser is missing them**.

Measured on `newspaper_ad_raw`, 160 saved ads:

| parsed_roles | count |
|---|---|
| `{"(Not specified)"}` | **98** |
| `{Accountant}` | 13 |
| `{For}` | 5 |
| `{"Marketing Manager"}` | 4 |
| `{Driver}` | 3 |
| `{"Computer Operator"}` | 3 |
| `{"Sales Executive"}` | 3 |
| `{Clerk}` | 2 |

61% resolve to "(Not specified)". Dropping on that today would delete 59% of
leads, nearly all of which state a role plainly.

Real ad text from the same run, all currently unparsed:

- `Reqs-fem-PET, PGT, PRT, NTT, Spl.Edu, Lib, Sanskrit & Male`
- `REQD (F) PGT Eco, History, TGT Sc, PET(F), Sp. Educator, Office Asst.`
- `+ Qualified Nurse + Accountants Apply at: hr@tips.edu.in`
- `Principal/Vice Principal resume.pps1234@gmail.com APEEJAY SCHOOL Saket`

Two separate defects: the vocabulary does not cover Indian job abbreviations,
and there is no stopword guard, which is why the literal word `For` is being
stored as a job title five times.

## Step 1 — report only

1. The current `extract_roles()` function in full, quoted.
2. Any role vocabulary list it uses, quoted.
3. Whether it can return more than one role per ad, and how it joins them.
4. Where `"(Not specified)"` is assigned.

Stop after reporting.

## Step 2 — fix `extract_roles()`

### 2a. Expand the vocabulary

Cover at minimum these, case-insensitive, matching as whole tokens so `PET` does
not match inside another word:

**Education**: PGT, TGT, PRT, NTT, PET, Principal, Vice Principal, Special
Educator, Spl.Edu, Sp. Educator, Librarian, Lib, Lab Assistant, Lab Attendant,
Sports Coach, Counsellor, Warden, Lecturer, Professor, Faculty, Teacher,
subject-qualified forms such as `PGT Eco`, `TGT Sc`, `PGT English`.

**Medical**: Nurse, Staff Nurse, GNM, B.Sc Nursing, ANM, RMO, Resident Medical
Officer, MBBS, BAMS, BDS, Pharmacist, Lab Technician, Radiographer,
Physiotherapist, Ward Boy, OT Technician.

**Commercial and admin**: Accountant, Accounts Assistant, Audit Assistant, Audit
Executive, Tally Operator, Computer Operator, Data Entry Operator, Receptionist,
Office Assistant, Office Asst, Clerk, Admin Executive, Store Keeper, Purchaser,
Cashier, Telecaller, Back Office.

**Sales and field**: Sales Executive, Marketing Manager, Field Officer, Business
Development Executive, Area Manager, Counter Sales.

**Technical and industrial**: Site Engineer, Site Supervisor, Civil Engineer,
Electrical Engineer, Mechanical Engineer, Estimation Engineer, BOQ Engineer,
Interior Designer, Draughtsman, Fitter, Welder, Electrician, Machine Operator,
Quality Chemist, Production Supervisor, Technician, Helper.

**Service**: Driver, Security Guard, Guard, Peon, Cook, Housekeeping, Attendant,
Delivery Boy.

### 2b. Handle multi-role ads

`Reqs-fem-PET, PGT, PRT, NTT, Spl.Edu, Lib, Sanskrit` is **seven** roles, not
one. Split on commas, slashes and the ampersand, then match each fragment.
Deduplicate. This matters because `roles_count` feeds the score.

### 2c. Add a stopword guard

Reject anything that is only a stopword or a fragment: `for, to, at, in, on,
the, and, with, from, of, or, a, an, is, are, req, reqd, wanted, required,
urgent, immediate, apply, send, contact, email, call`. A role must be a real
title, not a connective. That is what is producing `{For}`.

Also reject single tokens under 3 characters, and anything that is purely
digits or punctuation.

### 2d. Keep honest nulls

If nothing matches after all of the above, return an empty list. Do **not**
invent `"(Not specified)"` as a value. An empty list is the honest answer and
Step 3 depends on it being distinguishable.

## Step 3 — apply Anirban's drop rule

After 2d, an ad with no resolvable role is dropped with a new reject reason
`no_role`. Add it to the `reject_reason` vocabulary alongside the existing
`enterprise, government, no_contact, size_gate, coaching_centre, dupe,
low_score, other`.

**Order matters.** Drop for `no_role` only after the role parser has had its
full chance, so this gate never fires because of a vocabulary gap.

## Step 4 — measure and report

Re-run extraction over everything in `sweep.db` and report, before and after:

- distribution of `parsed_roles`, same shape as the table above
- how many ads now resolve at least one role, as a percentage
- how many are dropped as `no_role`
- total qualified leads, and ICP-qualified

**Acceptance, all four of these must parse correctly:**

| Ad text | Expected |
|---|---|
| `Reqs-fem-PET, PGT, PRT, NTT, Spl.Edu, Lib, Sanskrit` | 7 roles including PET, PGT, PRT, NTT |
| `REQD (F) PGT Eco, History, TGT Sc, PET(F), Sp. Educator, Office Asst.` | PGT, TGT, Special Educator, Office Assistant at minimum |
| `+ Qualified Nurse + Accountants` | Nurse and Accountant |
| `Principal/Vice Principal` | Principal and Vice Principal |

And `{For}` must no longer appear as a role anywhere.

Do not run the write. Report the numbers and wait.

## Rules for this task

- Work only inside `/root/projects/lead-manger`, and only in `extract.py`.
- Do not modify `sweep.py`, `dedup.py`, `run_radar.sh` or the OCR service.
- Do not write to any database in this task.
- Confirm you are on `main` before committing. `git add -f` for the .py.
- One step per reply. Finish a step, report, and wait.

## Acceptance

The four sample ads parse correctly, `{For}` is gone, ads with genuinely no role
are dropped as `no_role`, and the before-and-after role distribution is reported
from real output rather than asserted.
