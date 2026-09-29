# bidscout — status

**Update this file at the end of every session.** It is the first thing to
read when picking the project up again.

---

## Read this first (27 September 2026)

The folder `D:\DS ML\bidscout` did not exist until today. The code described
in the earlier session log was never saved to disk, so it is gone.

What you have now is a **rebuild from the written record**, not a recovery.
It was built in the cloud on 27 September 2026 from `docs/data-sources.md`
and the earlier status notes. That means:

- Everything **offline is real and checked**: 65 tests pass, `ruff` is clean,
  and `make demo` runs the whole pipeline end to end.
- Everything **live is unchecked**. The cloud has no access to
  e-licitatie.ro, so no call in `sicap/client.py` has been run against the
  portal in this rebuild. The endpoints and field names come from the spike
  notes of 20 September, which were verified then.
- The earlier "112 tests" and "200 notices stored" are **history, not the
  present state**. This repository has 65 tests and an empty database.

First job next session: run `bidscout watch --days 1` on your machine and
fix whatever the portal has moved. Until then, treat section 2 of
`docs/data-sources.md` as a good hypothesis.

---

## What this is

A tool that watches Romanian public tenders (SEAP / SICAP), reads each new
one, compares it against your company, and answers one question: **should
you bid?**

Two goals, in order:

1. A portfolio project good enough to win freelance work.
2. If it earns it, a paid tool for small companies and bid consultants.

---

## Where we are

| Piece | State | Checked how |
|---|---|---|
| Talking to SEAP | Code written, **not run against the portal** | — |
| The traps are guarded | Working | 12 offline tests |
| Reading the requirements out of a tender | Working | 11 offline tests on fixtures |
| Deciding GO / CHECK / NO-GO | Working, 3 gates + a score | 7 offline tests |
| Storing what we find | Working | 7 offline tests |
| Scoring from what we stored | Working, no requests to SEAP | 5 offline tests |
| The command line | Working offline | 6 offline tests |
| Writing the bid documents | Not started | — |
| A web page anyone can look at | Not started | — |
| Direct purchases | Mapped, not wired in | — |
| Reading the PDFs (the other 40%) | Not started | — |

**65 automatic tests, all offline, all passing.** `ruff` clean at line
length 100.

---

## What works today

```bash
make install && make demo
```

- **Score stored tenders** — GO, CHECK or NO-GO, a score out of 100, the
  number behind the decision, and the buyer's own sentence.
- **Explain one verdict** — every reason with its quote and its source field.
- **Watch the portal** — polls a publication window and stores what is new.
  *Written but not yet run against the live portal.*
- **See what the database holds** — `bidscout stats`.

Your company lives in one plain file (`profile.yaml`). The rules live in
another (`rules/it.yaml`). Neither needs a programmer.

---

## What the code enforces

Each of these guards a trap that cost real time, and each has a test named
after the behaviour it defends.

- `sicap/client.py` is the only module that knows a SEAP URL.
- An unknown **or known-ignored** filter name raises `UnknownFilter`. The
  portal answers a bad key with the unfiltered set, so a typo would otherwise
  look like a working query.
- `total: 3000` with `searchTooLong: true` raises `SearchTooWide`. It is a
  cap, not a count. A total sitting exactly on the cap is refused too.
- A `null` notice view raises `NoticeNotFound` instead of travelling into the
  parser as `None`.
- Romanian amounts ("2.700.000,00 Lei") are read as Decimal, never as float.
- A bare number with no currency and no thousand groups is **not** money.
  *(Found by the new suite on 27 September: years like 2023, 2024, 2025 were
  being read as sums.)*
- A requirement with no quote cannot be constructed at all.
- A notice with no stored Section 3 is skipped and counted, never scored.

---

## What we learned (from the 20 September spike — still to re-confirm)

- **60% of tenders can be decided without opening a PDF.** The buyer's
  requirements arrive as text in the portal's own JSON.
- **The daily volume is not in contract notices.** About one IT contract
  notice a day. The real flow is in *direct purchases*.
- **Simplified notices count.** 60% of everything published, and better
  covered than full ones (68% vs 46%).
- **Every tender has its documents attached** — 100% of the sample.
- **The gate that stops small companies is not turnover.** Turnover appears
  in 10% of tenders. What bites is past experience (52%) and the cash deposit
  (21%).

---

## Immediate next steps

In order. Each one is a session or less.

1. **Re-verify against the live portal.** Run `bidscout watch --days 1` on
   your machine. Fix any endpoint or field that has moved, and correct
   `docs/data-sources.md`. Nothing below is worth doing before this.
2. **A web page.** One page: your company on the left, today's tenders ranked
   on the right, click one to see why. This is the thing you send a link to.
3. **Direct purchases.** The high-volume channel, already mapped, not yet
   connected. This is what would make somebody open the app daily.
4. **The document checklist and the questions.** For a GO tender: what you
   must produce, by when, and which questions are worth asking the buyer.
5. **An alert.** Email or desktop, when something new scores GO.

---

## Longer term

- **The other 40%.** Tenders whose requirements are only in the PDF. Needs
  document reading, OCR, and a language model — with the same rule as now:
  the model reads, the rules decide, every fact keeps its quote.
- **Fill the DUAE.** The form comes as a structured XML file.
- **Check the scoring against history.** Eight years of past results are
  public. Compare what the tool would have said with who actually won.
- **Put it online.** A hosted version with the watcher on a schedule.
- **A second sector.** By design that is a new rules file, not new code.
- **Accounts, payment, three to five pilot users.**
- **The case study.** The write-up, a short video, one article.

---

## Open questions

- Simplified notices (`sysNoticeTypeId` 17, prefix `SCN`) have no working
  detail endpoint. `getPubCNoticeView` returns `null`.
- Direct purchases: the publication-date and CPV filter names are unknown.
- Two notice types not identified: `type 12`, and `RFD…`.
- `--cpv` on the database matches the **primary** CPV only, because secondary
  codes are not stored yet. The command prints this limit.
- The turnover wording is not always machine-readable. Those need the model.

---

## Ground rules for this project

1. **Anything Claude checks, Gabriel must be able to check.** Every finding
   becomes a command or a test in the repo, not a claim in a document.
2. **Never say "you do not qualify" when the honest answer is "we could not
   tell".** A missing fact or an unreadable sentence produces CHECK.
3. **Keep the raw data for ever.** `notices.raw` and `sections.section3_raw`
   are never dropped. A parser rewrite is replayed from disk.

A fourth, learned today:

4. **The repository is the project.** Work that is not written to
   `D:\DS ML\bidscout` does not exist. Save and push at the end of a session.

---

## Session log

### Session 1 — 20 September 2026

Mapped the portal's data service from scratch. Found three traps: a required
header, a filter the server silently ignores, and a "total" that is really a
cap. Measured machine-readable coverage at 60%. Built a decision engine and
storage. **None of this reached disk.**

### Session 1b — 21 September 2026

Drew the target product as a clickable sample screen (`docs/mockup.html`).
**Lost with the rest.**

### Session 2 — 22 September 2026

`bidscout score` reading the database by default; skip-and-count for unread
notices. **Lost with the rest.**

### Session 3 — 27 September 2026 (rebuild)

Two scheduled runs earlier in the day did nothing: the task had the folder
listed but was never set to require the computer, so each run started in the
cloud with no file bridge at all. Gabriel then found the folder had never
existed, created it, and asked for a rebuild.

Rebuilt the project from `docs/data-sources.md` and the status notes:

- `sicap/` — client, filter guard, error types. Every trap from the spike is
  a named error with a test. **Not run against the live portal.**
- `extract/` — HTML stripping, Romanian money parsing, gate extraction.
  Every requirement keeps its quote and its source field.
- `decide/` — YAML rule set, hard gates, 0-100 score. Ground rule 2 is
  enforced here and tested from four directions.
- `store/` — SQLite, raw JSON columns, new-vs-seen, saved verdicts.
- `pipeline.py`, `cli.py`, `scripts/demo.py`, `Makefile`.

**65 tests, all passing. `ruff` clean.** The suite found one real bug while
being written: bare four-digit years were read as money, so a sentence naming
"2023, 2024, 2025" produced a 2,025 RON turnover requirement. Fixed, and
guarded by `test_a_bare_number_needs_a_currency_or_grouping_to_count_as_money`.

Could not do, and why:

- **No live check of anything.** The cloud sandbox cannot reach
  e-licitatie.ro. No `probe`, `watch`, `search` or `pull` was run.
- **The old code was not recovered.** It was not on disk and not reachable.
  This is a fresh implementation of the same specification, so the file names
  and the test count differ from session 2.
- **`docs/mockup.html` is gone.** Step 2 (the web page) has no design brief
  any more. Redraw it, or build the page directly from the `scores` table.

Next session starts at **immediate step 1: re-verify against the live
portal**, then step 2, the web page.
