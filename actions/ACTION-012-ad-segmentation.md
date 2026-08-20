# ACTION-012 — Fix ad segmentation

Owner: Anirban
Repo: anirban475/lead-manger
File: `jd-lead-newspaper/sweep/extract.py`
Working copy on VPS: `/root/projects/lead-manger`. Confirm you are on `main`.

## Why this exists

This blocks Anirban's rule that ads without a job role should be dropped. That
rule is currently disabled (`--drop-no-role`, default off) because the parser
still loses roles that are plainly printed.

Role extraction was already rebuilt in ACTION-010 and resolution went from 28.9%
to 54.2%. The remaining 45.8% are mostly **not** missing vocabulary. They are
ads whose role was cut out of the extraction window.

## The defect

Segmentation is contact-anchored: every phone and email is an anchor, and the
candidate ad is roughly 400 characters before the anchor and 100 after.

In a boxed newspaper classified the job title is the **headline at the top** of
the box while the phone and email sit at the **bottom**. A tall ad therefore
loses its own headline. OCR reading order makes it worse, because adjacent
columns interleave, so the true start of the ad can be much further back than
400 characters of running text.

Three real examples that resolve zero roles purely because of windowing:

```
WALK-IN INTERVIEW Mon to Sat, 9 to 2 Mail us at :- jobs@abhinav.ac.in
ABHINAV VIDYALAY -P-36, MIDC-2, Dombivli East
```
```
Salary will be commensurate with qualification and experience.
Only suitable candidates may apply with their typed updated CV
```
```
B/D, Shalimar Bagh, Delhi-110 088 ... Place of posting - YMCA Public School,
Nizamuddin East
```

Each is a fragment of a real ad, not an ad without a role.

## Step 1 — report only

1. The current segmentation function in full, quoted, including the window
   constants.
2. How overlapping windows are merged today.
3. Of all ads currently resolving zero roles, what proportion contain a
   recruitment trigger word (`required`, `reqd`, `wanted`, `walk-in`,
   `vacancy`, `hiring`) somewhere in the window. A high proportion means the ad
   start is inside the window and only the title is missing; a low proportion
   means the window is missing the ad start entirely. This number decides which
   approach below is right.

Stop after reporting.

## Step 2 — build, measured against two metrics

Whatever approach you take, it must be judged on **both** of these, reported
before and after:

- **Role resolution rate**, currently 54.2%. Should go up.
- **False-merge rate**: two adjacent, unrelated ads combined into one lead.
  Sample 30 segments by hand and count how many contain two different
  employers. This must not get materially worse.

A wider window trivially raises the first and quietly wrecks the second. Both
numbers together, or the change is not evidence of anything.

### Approaches, cheapest first

**A. Widen the backward window.** Try 800 and 1200 characters. Cheap to test,
tells you quickly whether the problem is simply size.

**B. Segment on structural cues instead of a character count.** Most classifieds
begin with a recognisable marker: an ALL-CAPS line, or one of
`REQUIRED / REQD / WANTED / REQUIRES / WALK-IN / HIRING / SITUATION VACANT`.
Cut the ad at the nearest preceding marker rather than a fixed offset.

**C. Invert the anchor.** Anchor on the recruitment marker or the role itself as
the ad *start*, then attach the nearest following contact. This suits classified
layout better, since the headline is the reliable opener, but it will miss ads
whose headline OCR'd badly.

I expect B to win, with the character count kept only as a fallback bound so a
missing marker cannot swallow half a page. Do not implement C without reporting
first.

### Non-goals

Do not change the matrimonial, property or hiring-verb classifiers. Do not
change the role vocabulary. Do not enable `--drop-no-role`. Do not write to any
database.

## Step 3 — commit

Commit `extract.py` only. `.gitignore` line 31 is `*.py`, so `git add -f`.
Paste `git show --stat HEAD`.

## Acceptance

Role resolution above 54.2%, false-merge rate measured and not materially worse,
and all three example fragments above now resolve at least one role. Report both
numbers from a real run, not asserted.
