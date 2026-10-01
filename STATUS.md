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
| Tracing a verdict to its sentences | Working, a `requirements` table | 10 offline tests |
| Multi-lot tenders | Flagged, not read: they are held at CHECK | 5 offline tests |
| Scoring from what we stored | Working, no requests to SEAP | 5 offline tests |
| Measuring how well we read | Working, on 3 labelled notices | `make eval` + 17 tests |
| The command line | Working offline | 11 offline tests |
| Writing the bid documents | Not started | — |
| A web page anyone can look at | Not started | — |
| Direct purchases | Mapped, not wired in | — |
| Reading the PDFs (the other 40%) | Not started | — |

**105 automatic tests, all offline, all passing.** `ruff` clean at line
length 100.

---

## What works today

```bash
make install && make demo
```

- **Score stored tenders** — GO, CHECK or NO-GO, a score out of 100, the
  number behind the decision, and the buyer's own sentence.
- **Explain one verdict** — every reason with its quote and its source field.
- **Trace a verdict** — `bidscout requirements <id>` prints every figure the
  last score read, with the buyer's sentence and the Section 3 field it came
  from. No parser run, no profile, no network.
- **Watch the portal** — polls a publication window and stores what is new.
  *Written but not yet run against the live portal.*
- **See what the database holds** — `bidscout stats`.
- **Measure how well it reads** — `bidscout eval` prints, per gate, how
  often a figure is found and how often it is right, against notices
  labelled by hand in `eval/cases/`. `bidscout capture <id>` turns a
  stored Section 3 into a new case to label.

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
- An unlabelled evaluation case is listed, never counted. Otherwise every
  capture would raise the accuracy figure without anybody checking it.
- A figure the buyer never wrote is counted as **invented**, in its own
  column, separately from a miss. A miss costs an opportunity; an
  invention can push a verdict to NO-GO on a number nobody wrote.
- A label amount written as an unquoted JSON number is refused, because
  `json` reads it as a float and it is then not the number that was typed.
- A tender **split into lots** is never a NO-GO. The notice-level turnover or
  experience figure may be the total for every lot, while you would bid for
  one, so the verdict is held at CHECK and the lots are listed as unresolved.
  *(1 October 2026.)*
- A **stored** requirement amount is a TEXT column rebuilt as `Decimal`. As a
  REAL, 2.700.000,00 Lei would come back as a float and move a hard gate by a
  fraction of a leu.
- An **empty requirements trace means "not scored yet"**, never "the buyer asks
  for nothing". `bidscout requirements` says which, and exits 1.
- A database written **before** a column existed is migrated by adding the
  column, never by rebuilding the table. Ground rule 3 applies to migrations:
  no stored row is dropped to make one simpler.

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

In order. Each one is a session or less. The order is deliberate: the data
model, the pipeline and a number for accuracy come before anything anybody
looks at. A pretty page over a parser nobody has measured is worth nothing.

1. **Re-verify against the live portal.** Run `bidscout watch --days 1` on
   your machine. Fix any endpoint or field that has moved, and correct
   `docs/data-sources.md`. *Needs the portal, so only Gabriel can do it.*

2. ~~**An accuracy harness.** `bidscout eval` over a labelled fixture set:
   per-gate coverage and precision, printed as a table, plus
   `bidscout capture <id>`.~~ **Done 30 September 2026.** Built and tested
   offline. *It is only loaded with three labelled cases, so the table is a
   smoke test, not a measurement.* **Next: capture and label about thirty
   real notices** — `bidscout capture <id> --live` on your machine, one per
   notice, then fill the labels in. Until then the "60% coverage" figure is
   still a guess.

3. **Close the data-model gaps that already bite.** Two of three done on
   1 October 2026; the first bullet is still open and needs the portal.
   - Secondary CPV codes are not stored, so `--cpv` silently misses any
     notice whose IT code is not the primary one. **Still open, and blocked:**
     the search item carries one CPV field only (`cpvCodeAndName`), and
     nothing in `docs/data-sources.md` says where a secondary code lives. It
     needs one live look at a notice that has one — either the detail view or
     the lot list. Guessing a field name offline would be an invented fact.
   - ~~Lots are not modelled at all (`hasLots`), so a multi-lot tender is
     scored as one thing.~~ **Done 1 October 2026.** `hasLots` is read,
     stored and refreshed on a re-poll, and a multi-lot tender is held at
     CHECK instead of being measured against a figure that may cover every
     lot. The lot *contents* are still unread — that is the next piece, and
     it needs the `GetSection22LotList` field names from a live call.
   - ~~Requirements are re-parsed on every score and never stored, so a
     verdict cannot be traced back without redoing the work. Give them a
     table with their citations.~~ **Done 1 October 2026.** A `requirements`
     table, written on every score, read by `bidscout requirements <id>`.

4. **Wire the ingest pipeline end to end.** `watch` stores notices, but
   nothing fetches their Section 3 or their file list, so the database fills
   with notices the scorer then skips. Add `bidscout fetch`: for every
   stored notice with no Section 3, pull the section and the document list
   and store both. Build and test it offline against a fake transport; run
   it live on your own machine.

5. **Direct purchases.** The high-volume channel, already mapped, not yet
   connected. Model, store, and a short rule set — there is no Section 3 to
   read, so the gates differ.

6. **Simplified notices (SCN).** 60% of everything published. The detail
   endpoint is still unknown, so the model and the skip-and-count path can
   be built now and wired when the endpoint is found.

7. **A web page.** One page: your company on the left, today's tenders ranked
   on the right, click one to see why. This is the thing you send a link to.
   The original mockup was lost, so this needs a fresh design.

8. **The document checklist and the questions.** For a GO tender: what you
   must produce, by when, and which questions are worth asking the buyer.

9. **An alert.** Email or desktop, when something new scores GO.

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

### Session 4 — 30 September 2026 (cloud, no portal access)

Picked immediate step 2, the accuracy harness. Step 1 (re-verify against the
live portal) was skipped, not done: the cloud sandbox cannot reach
`e-licitatie.ro`, so it stays Gabriel's job on his own machine.

Built:

- `accuracy/cases.py` — the labelled-case format. One file per notice holding
  the raw Section 3 (ground rule 3) *and* the labels a person wrote. A label
  amount must be a quoted string; an unquoted JSON number is refused with an
  instruction, because `json` reads it as a float and it is then no longer
  the number the labeller typed.
- `accuracy/report.py` — coverage and precision per gate, printed as a table,
  with three failure counts kept apart: `missed`, `invent` and `spur`. An
  invented figure is the one that can push a verdict to NO-GO on a number the
  buyer never wrote, so it has its own column and its own test.
- `accuracy/capture.py` — `capture_case`, from the database by default and
  from the portal with a client. The client is a one-method protocol, so the
  live path is tested offline with a fake and no socket is opened.
- `bidscout eval` and `bidscout capture <id> [--live]`, `make eval`,
  `eval/README.md` explaining how to label, and `errors.SectionNotStored`.
- `eval/cases/` seeded with three cases: two transcribed from the
  20 September spike and one written by hand carrying two traps in one notice
  (a turnover rule whose only numbers are the three financial years, and a
  guarantee stated in euro).

`bidscout eval` today: coverage 100% and precision 100% on every gate,
0 invented, 0 spurious, 0 missed — **on three cases**. That is a smoke test.
The number only starts meaning something at about thirty.

**65 tests before, 87 after. `ruff` clean.** No existing test was changed or
weakened.

Could not do, and why:

- **No live check of anything**, again. No `watch`, `probe`, `capture --live`
  or any other call to the portal was run. The `--live` path is written and
  tested against a fake transport; it has never spoken to SEAP.
- **The init-notice-id question is still open.** `pipeline.notice_from_item`
  reads `init_notice_id` from the item's `noticeId` (384463 in the fixture),
  while `tests/fixtures/section3_cn1096282.json` carries
  `initNoticeId: 1096282`, which is the *cNoticeId*. One of the two is wrong
  and only a live call can say which. `capture_case` prefers the stored init
  id and falls back to the id it was given, with a comment saying so, and the
  test asserts today's behaviour rather than a guess about the portal.
- **Three cases is not a measurement.** Labelling is the bottleneck now and
  it needs a human who can read the Romanian sentence.

Next session starts at **immediate step 1** (live re-verify, Gabriel's
machine), then **step 3** (secondary CPV codes, lots, stored requirements).
Labelling thirty notices for the harness can happen in parallel and needs no
code.

### Session 5 — 1 October 2026 (cloud, no portal access)

Picked immediate step 3, the data-model gaps. Step 1 (re-verify against the
live portal) was skipped again, not done: the cloud sandbox cannot reach
`e-licitatie.ro`, so it stays Gabriel's job on his own machine. Step 2 is done.

Two of step 3's three bullets are now closed.

**Lots.** `hasLots` is read from the search item into `Notice.has_lots`, stored
in its own column, and passed to the engine. A tender split into lots is now
held at **CHECK** and the lots appear in `unresolved`, because the turnover or
experience figure in Section 3 may be the total for every lot while you would
bid for one — comparing a company against that total and printing NO-GO is the
"we could not tell" that ground rule 2 forbids. The test asserts both halves:
the same notice *without* lots is still a legitimate NO-GO, so a change that
turned every verdict into CHECK could not pass as a fix.

`has_lots` is the one convenience column refreshed when a notice is seen again,
because it changes the verdict: a corrigendum that splits a tender must not
leave yesterday's GO standing.

**The requirements trace.** A `requirements` table, written on every score,
holding each figure with the buyer's sentence, the Section 3 field, the
confidence and the time it was read. `bidscout requirements <id>` prints it —
no profile, no rules, no parser run, no network. The table is *derived*: the
scorer still re-reads `sections.section3_raw` every run, so an extractor fix
still applies immediately, and the raw section remains the only source of
truth. `amount` is TEXT rebuilt as `Decimal`; as a REAL it would come back as a
float and move a hard gate by a fraction of a leu. An empty result is reported
as "not scored yet", never as "the buyer asks for nothing".

**A migration step.** The schema is applied with `CREATE TABLE IF NOT EXISTS`,
which does nothing to a table that already exists, so `has_lots` would have
been missing from any database written earlier and the first query naming it
would have failed with "no such column" — on the one machine holding the real
data. `Store` now adds missing columns on open, from a declared list, and a
test opens a database built with the old DDL and checks the old row survives.

**87 tests before, 105 after. `ruff` clean.** No existing test was changed or
weakened; `make demo` still runs end to end.

Could not do, and why:

- **Secondary CPV codes — blocked, not skipped.** The search item has one CPV
  field (`cpvCodeAndName`) and `docs/data-sources.md` records no secondary-code
  field anywhere. Storing a list needs one live look at a notice that has a
  secondary code, to learn where the portal puts it. Writing a field name from
  guesswork would be an invented fact in a project whose value is that its
  claims can be checked, so it was left alone. `--cpv` still prints its limit.
- **The lot contents are still unread.** Only the flag is modelled. Reading the
  per-lot requirements needs the `GetSection22LotList` response shape, which is
  a live call. Until then a multi-lot tender is an honest CHECK, not a score.
- **No live check of anything**, a third time. No `watch`, `probe`, `fetch` or
  `capture --live` was run. Nothing in this session touched the portal.
- **Still three labelled cases.** Labelling needs a human who reads Romanian.

Next session starts at **immediate step 1** (live re-verify, Gabriel's
machine). After that, either the secondary-CPV field and the lot list — both
unblocked by the same live look — or **step 4**, `bidscout fetch`, which is the
piece that stops the database filling with notices the scorer then skips.
