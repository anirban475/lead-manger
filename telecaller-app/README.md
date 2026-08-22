This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## Brand rule: ownership is one, eligibility can be two

A lead carries two brand fields and they answer different questions.

| Column | Holds | Answers |
|---|---|---|
| `leads.brand` | Exactly one brand, always | Who owns it. Drives attribution, cost and CAC |
| `leads.eligible_brands` | `text[]`, one or both | Who is allowed to call or email it |

**The queue filters on eligibility, never on ownership.** Everything that reports
money keeps reading `brand` and needed no change when this went in.

**Never make `brand` an array, and never add a second row for the same company
to represent the second brand.** CAC is spend divided by customers won. If two
brands own the same lead the company is counted twice and both brands' cost per
customer goes wrong. A duplicate row is worse: dedup collapses on contact, so it
either merges away or inflates both brands' spend against one company and has
the telecaller ring them twice.

Who sees what is read from `app_users.brand` at query time rather than from the
session cookie, so reassigning a caller takes effect on their next page load and
an old cookie cannot leak the other brand's leads. `role='admin'` sees both.

Side effect worth keeping: if Jobdrive works a shared lead and it goes nowhere,
Amatec still has it, because eligibility never changed. Before this, that lead
was simply gone.

Two traps, both already paid for:

- Use `cardinality()`, not `array_length()`, in any constraint on
  `eligible_brands`. `array_length('{}',1)` is NULL and a CHECK passes on NULL,
  so an empty array slips through and hides the lead from everyone.
- `v_touchpoint` in marketing-360 derives brand as
  `CASE WHEN l.brand='amatec' THEN 'Amatec' ELSE 'JobDrive' END`. Anything not
  literally `amatec` lands in JobDrive's numbers silently. Keep
  `eligible_brands` out of that view.

## Call quality lives in a second database

The cockpit connects to `leads`. Call scores, transcripts and coaching analysis
live in `telecaller_coaching`, written hourly by the n8n ingestion workflow. Same
Postgres instance, different database, and a Postgres connection is bound to one
database for its lifetime, so `leads` cannot join to it.

`lib/coachingDb.ts` opens a second pool. It derives the coaching connection
string from `DATABASE_URL` by swapping the database name in the path, with
`COACHING_DATABASE_URL` as an override. There is deliberately no new credential:
`leads_user` was granted `CONNECT`, `USAGE` on schema public, and `SELECT` on
`agents`, `calls` and `chat_messages` (see `sql/02_agents_app_user_email.sql`).

`agents.app_user_email` is the only link between the two databases. It maps a
coaching agent to an `app_users` row by email. Keep it populated when a
telecaller is onboarded, or their calls become invisible to the cockpit while
still being ingested perfectly happily.

Traps worth knowing before touching any of this:

- **Do not join across the two databases in SQL.** There is no FDW and there
  should not be one. `agents` and `calls` are both in `telecaller_coaching`, so
  every dashboard query is single database. The session already tells you who is
  logged in, which is the only thing `leads` contributes.
- **`analysis->>'talk_ratio'` of `'0/0'`, `'100/0'` or `'0/100'` means the call
  never happened**: voicemail, IVR, hold music or silence. Exclude these from
  every average. Excluding is correct, deleting is not.
- **The Saturday weekly report task deletes those junk rows outright.** Any view
  built on this data will see history shrink behind it every week. Changing that
  delete to a flag is the right fix and has not been done yet.
- **`talk_ratio` is the model's guess from reading a transcript, not a
  measurement.** The first number is the agent's share and lower is better. Show
  it as an estimate. Do not let anyone be judged on it.
- **`duration_sec` is null on every row.** Call volume means a count of calls,
  never minutes.
- **`key_issues` is free text and it is a mess.** 1,371 distinct strings across
  2,499 rows. "Lack of engagement" alone is split across four near-identical
  wordings totalling 228 calls. Counting the raw strings produces a list of
  one-offs that nobody can act on. A fixed category set is needed before any
  "what am I getting wrong" panel is worth building.

Baseline as of 22 Aug 2026, 90 day window, for sanity checking any future change:
Bhratti Raval 986 calls, average score 4.39, average objection handling 3.32
against a target of 6, average agent talk share 57.12. `tools/perf-check.mjs`
prints all of this and exits non-zero if the data layer breaks.
