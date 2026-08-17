# ACTION-001 — Get indupaper.com's full newspaper catalog

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

We are migrating the Newspaper Radar source from ads2publish.com (proven
unreliable, does not mirror what actually ran in print) to indupaper.com
(proven live for Amar Ujala, Rajasthan Patrika and Dainik Jagran via manual
DevTools capture on 2026-08-17, see `jd-lead-newspaper/ocr-poc/source-contracts-2026-08-17.md`).

That manual capture does not scale to the full 67-paper list in the Newspaper
Radar Playbook. We have been guessing indupaper.com's paper slugs one at a
time by matching against our 67 names. That is pure guesswork: we do not
actually know indupaper's own catalog. Getting the full catalog first removes
the guessing entirely and turns the next task (matching + endpoint capture)
into a lookup instead of a search.

## Step 1 — report only, no changes

1. Fetch `https://www.indupaper.com/sitemap.xml`. If it exists, list every
   `.html` URL under it that looks like a newspaper page (exclude blog posts,
   contact, post-news, and state-only pages like `epaper-rajasthan.html`).
2. If there is no sitemap, or it is incomplete, fetch `https://www.indupaper.com/`
   and any "browse all newspapers" or footer link you find, and extract every
   newspaper page link from there instead. Note which method you used.
3. For every newspaper page found, report its display name and its slug (the
   filename before `.html`), for example `Dainik Bhaskar | dainik-bhaskar`.
4. Report the total count of newspaper pages found.

This is read-only. Use `curl` or a script, not a browser. Do not write any
file, do not commit anything, do not modify any service.

Report the full list as plain text, one paper per line: `<name> | <slug>`.
Stop after reporting and wait.

## Rules for this task

- Work only inside `/root/projects/lead-manger` if you need scratch space for
  a script. Touch nothing else on the VPS.
- Do not restart, stop or reconfigure any service.
- This step makes no writes at all — no files, no commits. If your method
  requires a temp script, delete it before reporting.
- One step per reply. Finish Step 1, report, and wait for the next
  instruction. Do not proceed to any follow-up work on your own.

## Acceptance

Done when the reply contains a plain list of `<name> | <slug>` pairs covering
every newspaper indupaper.com hosts, plus a total count, and confirms nothing
was written or committed.
