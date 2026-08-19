# ACTION-005 — Correct the ICP rules, add a hiring-verb guard, fix the business-email score

Owner: Anirban
Repo: anirban475/lead-manger
File: `jd-lead-newspaper/sweep/extract.py`
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

Three separate defects are suppressing real leads. All three are measured, not
suspected. Together they take survivors from 31 to 71 on the same 99 pages.

### Defect 1: every school and college is dropped as a coaching centre

`EDU_MARKERS` lumps `school`, `college`, `principal`, `cbse`, `icse`,
`vidyalaya`, `convent`, `faculty`, `teacher`, `pgt`, `tgt` in with `coaching`
and `tuition`, and `main()` drops anything matching the whole list as
`coaching_centre`.

**24 ads were dropped this way. Every one was a real school or college, not a
coaching centre.** Anirban's rule is that schools and colleges are valid
targets and only coaching centres should be dropped.

Casualties include Pinegrove School recruiting a Resident Medical Officer at
`office@pinegroveschool.com`, and HNB Garhwal University at
`recruitment.nt@hnbgu.edu.in`.

### Defect 2: hospitals are not ICP

Hospitals belong in the ICP. Anirban's reasoning: they need educated staff,
frequently have no dedicated HR function, and the screening load falls on a
doctor. That is precisely the Jobdrive buyer.

### Defect 3: the business-email bonus is +5 where the doctrine says +20

`jd-lead-newspaper/README.md`, under "Decisions worth not relitigating":

> **Business email outweighs every overload signal combined**, +20 against a +15
> cap. Overload measures hiring pain, a business domain measures ability to pay,
> and the second decides whether a lead is worth anyone's time.

`score_lead()` awards `score += 5`. The threshold for warm is 50, so a 15-point
shortfall silently kills real leads sitting at exactly 40. All of these were
dropped as `low_score`:

| Company | Contact | The ad |
|---|---|---|
| Yardiprabhu | `hr@yardiprabhu.com`, 7045903247 | "A CA firm needs 10 fresh/experienced graduates as Audit Assistants" |
| Sarayan | `shweta.pandey@sarayan.in`, 7208063229 | "Req. Sr. Int. Des., BOQ & Est. Eng, Site Eng., Jr. HR asst, min 3 yrs exp" |
| Anemos | `hiring@anemos.in` | "Hands-on learning & mentorship. APPLY NOW" |
| Envirowater | `info@envirowater.in` | "Send your CV + recent photograph" |

## The trap in fixing defects 1 and 2

Widening the sector rules creates a new false-positive class, and it is not
hypothetical. Newspaper classifieds are full of **clinics advertising
treatments** and **schools advertising admissions**. Both carry the sector noun
and a phone number, and neither is an employer hiring.

Real example, Hindustan Delhi 2026-08-16 page 10, ads for बवासीर (piles),
सोरायसिस (psoriasis), निसन्तान and शुक्राणु कमी (infertility), SEX रोगी. Those
are doctors selling treatment to patients. Under a naive hospital rule they
score as ICP-qualified medical leads.

A second real example already in the low-score drops is `sietpanchkula`, whose
ad text is "required to submit semester fee of Rs. 32200 on the spot. The annual
fee of the Institute is Rs. 47200. Admission Helpline" — an admissions ad, not a
vacancy.

**The distinguishing signal is a hiring verb, never the sector noun.**

## Step 1 — report only, no changes

Report, quoted verbatim from `jd-lead-newspaper/sweep/extract.py`:

1. The current `EDU_MARKERS` list.
2. The current `ICP_MARKERS` list.
3. The `score_lead` function in full.
4. The block in `main()` that applies `drop_counts["coaching_centre"]`.

Stop after reporting. Change nothing.

## Step 2 — build

### 2a. Narrow the education drop list to genuine coaching only

`EDU_MARKERS` becomes coaching only: `coaching`, `tuition`, `iit-jee`, `neet`,
`tutorials`, `entrance exam`, `coaching centre`, `coaching center`. Remove
school, college, principal, cbse, icse, vidyalaya, convent, faculty, teacher,
pgt, tgt, prt, ntt, academy, institute, education, teaching, professor,
lecturer, shikshan, vidyapeeth, pre-school, play school from the DROP list.

### 2b. Add formal education and healthcare to ICP

Add to `ICP_MARKERS`: `school`, `college`, `vidyalaya`, `convent`, `cbse`,
`icse`, `university`, `hospital`, `nursing`, `clinic`, `diagnostic`,
`pathology`.

### 2c. Add the hiring-verb guard — this is the important one

Introduce `HIRING_VERB_MARKERS`: `required`, `requires`, `wanted`, `vacancy`,
`vacancies`, `vacant`, `walk-in`, `walkin`, `recruitment`, `appointment`,
`resume`, `cv`, `apply`, `hiring`, `post of`, `interview`, `candidates`,
`applications invited`, `send biodata`, plus Hindi `आवश्यकता`, `चाहिए`,
`भर्ती`, `रिक्ति`.

**An ad may only be classified `recruitment` if it contains at least one hiring
verb.** A sector noun plus a phone number is not sufficient. Apply this before
the ICP test, so a clinic advertising piles treatment and a school advertising
admissions are both rejected regardless of how well they match ICP markers.

Record these as a new drop reason `advertisement_not_vacancy` and report the
count, so we can see how large the class is.

### 2d. Correct the business-email bonus

In `score_lead`, change the non-free-provider email bonus from `+5` to `+20`,
matching the documented rule. Change nothing else about the scoring.

### Non-goals

Do not change the matrimonial or property classifiers, they work. Do not change
the tier thresholds (70 hot, 50 warm). Do not change company-name resolution.
Do not write to any database.

### Test, and paste real output

Re-run over all 99 pages and report:

- the full before and after table: candidates, classification breakdown, every
  drop reason including the new `advertisement_not_vacancy`, survivors, hot,
  warm, ICP qualified
- confirmation that `coaching_centre` drops are now only genuine coaching
- confirmation that the matrimonial acceptance still passes, TOI Delhi
  2026-08-02 page 14 must still yield **0** survivors
- 10 sample survivors that are schools, colleges or hospitals, so we can eyeball
  that they are hiring rather than advertising

Expected direction, from a patched scratch copy already run at
`/root/coverage/test_v3.py`: survivors roughly 31 to 71, ICP roughly 7 to 27,
hot roughly 2 to 21. The hiring-verb guard will pull those numbers down
somewhat, which is correct and expected. Report what you actually get.

## Step 3 — commit

Commit `jd-lead-newspaper/sweep/extract.py` and the regenerated report. `.gitignore`
line 31 is `*.py`, so `git add -f` is required or the commit silently contains
nothing. Paste `git show --stat HEAD`.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not restart or reconfigure any pm2 process or the OCR service.
- Do not modify `sweep.py`, `app.py` or anything under `ocr-service/`.
- Do not write to any Postgres database.
- One step per reply. Finish a step, report, and wait.

## Acceptance

All four hold: `coaching_centre` no longer drops schools or colleges, hospitals
and schools appear among ICP-qualified survivors, a clinic treatment ad and a
school admissions ad are both rejected as `advertisement_not_vacancy`, and TOI
Delhi 2026-08-02 page 14 still produces 0 survivors.
