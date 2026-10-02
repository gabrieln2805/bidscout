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
| Filling in what the search leaves out | Code written, **not run against the portal** | `bidscout fetch`, 30 offline tests |
| Tracing a verdict to its sentences | Working, a `requirements` table | 10 offline tests |
| Multi-lot tenders | Flagged, not read: they are held at CHECK | 5 offline tests |
| Scoring from what we stored | Working, no requests to SEAP | 5 offline tests |
| Measuring how well we read | Working, on 3 labelled notices | `make eval` + 17 tests |
| The command line | Working offline | 15 offline tests |
| Writing the bid documents | Not started | — |
| A web page anyone can look at | Working, published from `docs/` | `make site` + 11 offline tests |
| Direct purchases | Mapped, not wired in | — |
| Reading the PDFs (the other 40%) | Not started | — |

**163 automatic tests, all offline, all passing.** `ruff` clean at line
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
- **Read what the search left out** — `bidscout fetch` takes every stored
  notice with no Section 3, pulls the section and the file list, and stores
  both. That is what turns a database full of notices the scorer skips into
  one it can rank. A notice already read is never asked for again, so a second
  run makes no request at all, and the command counts its queue before it
  builds a client — a test asserts it builds none. `--limit` bounds one run
  (default 50, `0` for all). *Written but not yet run against the live
  portal.*
- **See what the database holds** — `bidscout stats`.
- **Show it to somebody** — one static page, `docs/index.html`, built by
  `bidscout export` from the scored database. Your company on the left, the
  tenders ranked on the right, click one for the buyer's own sentences. No
  build step and no framework; GitHub Pages serves it from `/docs`.
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
- A requirement the buyer stated in **another currency** is never compared to
  a profile in lei. The rate that applies is the one on the notice's own date,
  which bidscout cannot verify, so it is CHECK and the reason names the
  currency the buyer actually wrote. *(1 October 2026.)*
- **No amount on the published page has been through a float.** Every figure in
  `docs/data.json` is a string, and the exporter refuses a float rather than
  publishing a rounded gate.
- **The page never reads the English to decide anything.** Each gate is marked
  from the `outcome` the engine computed, and every string from the portal
  reaches the DOM through `textContent`, never as markup.
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
- A Section 3 the reader **recognised nothing in** is CHECK, never GO. With no
  requirements read, every gate says "the buyer does not ask for one", nothing
  is unresolved, and the score alone decides — so an unreadable section used to
  come out GO. The guard is in `decide`, which is the one place that turns "we
  could not tell" into CHECK, so every command that stores a section is covered
  by it and the raw payload is still kept. A test puts a 2.7 million turnover
  rule in a Section 3 field no gate maps to and watches the verdict stay CHECK.
  *(2 October 2026.)*
- **Simplified notices are left out of the fetch queue in SQL**, not skipped
  inside the loop. They can never be fetched, so they never leave the queue;
  counted against `--limit` they would sit at the front of every run for ever
  and starve the 40% of notices that can be read.
- `--limit 0` means **every notice**, and is translated to "no limit" before it
  reaches SQLite. Passed through, `LIMIT 0` would read nothing and report an
  empty queue on a database full of unread notices. A negative limit is refused
  by the store, because SQLite reads one as no limit at all.
- The **file list is read group by group, not from a list of five group names**.
  A group the portal adds later — a clarification, most likely — would
  otherwise be dropped in silence.
- A file-list entry with **no URL and no GUID** is counted, not stored. The
  documents table is keyed on the GUID, so two such entries on one notice
  would collide and `INSERT OR IGNORE` would swallow the second.
- Every file-list field is **forced to a string** before it reaches SQLite,
  which refuses to bind a list or an object and raises far from the portal
  response that caused it.
- **One notice the portal refuses does not end a fetch run**, and an unexpected
  failure does end it, on purpose: repeating an unknown fault once per notice
  would be fifty pointless requests to somebody else's server.

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

4. ~~**Wire the ingest pipeline end to end.** `watch` stores notices, but
   nothing fetches their Section 3 or their file list, so the database fills
   with notices the scorer then skips. Add `bidscout fetch`.~~
   **Done 2 October 2026.** `bidscout fetch` works through every stored notice
   with no Section 3, newest first, bounded by `--limit` (default 50, `0` for
   all), skipping simplified notices it cannot read. Built and tested offline
   against a fake transport driven through the real client, and every new test
   was checked by breaking the behaviour it defends and watching it fail.
   *Not run against the portal — that still waits on step 1.*
   **Next: `bidscout watch --days 1 && bidscout fetch` on your machine**, then
   `bidscout score`. That is the first time this project will have scored a
   real tender.

5. **Direct purchases.** The high-volume channel, already mapped, not yet
   connected. Model, store, and a short rule set — there is no Section 3 to
   read, so the gates differ.

6. **Simplified notices (SCN).** 60% of everything published. The detail
   endpoint is still unknown, so the model and the skip-and-count path can
   be built now and wired when the endpoint is found.

7. ~~**A web page.** One page: your company on the left, today's tenders ranked
   on the right, click one to see why. This is the thing you send a link to.~~
   **Done 1 October 2026.** `docs/index.html`, one static file, no build step,
   reading `docs/data.json` from the new `bidscout export`. Turn it on at
   Settings → Pages → Deploy from a branch → `main` / `/docs`. It currently
   shows the demo fixtures scored against `profile.example.yaml`; it will show
   real tenders as soon as step 1 and step 4 have filled a database.

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

### Session 6 — 1 October 2026 (cloud, no portal access)

Gabriel asked for a front end he can put on GitHub Pages, before applying the
session 5 patch. Pages serves files and runs no Python, and the portal sends no
CORS headers, so the page cannot query the database or call SEAP. The seam is a
new command.

**`bidscout export`** (`src/bidscout/export.py`) scores the database offline and
writes one JSON file: the company, the rule set, the ranked tenders with their
reasons, quotes, source fields and requirement traces, the notices nobody has
read in full, and the file's own provenance — which database, which profile,
which rules, when, which version. Every amount is a string. The exporter refuses
a float outright, and a test walks the whole round-tripped payload to prove no
number in it is a float, so a figure added carelessly later fails the suite
rather than quietly rounding a hard gate on a public page.

**`docs/index.html`** is the page: one static file, no build step, no framework,
no dependency. Company and rules on the left, tenders ranked on the right, click
one for the buyer's own sentences with the Section 3 field beside each. It shows
the skipped notices rather than hiding them, and the footer states the four
ground rules. `make site` rebuilds it end to end; `make serve` shows it exactly
as Pages will. Light and dark, checked at 1280px and at phone width in a real
browser.

Two things the page is not allowed to do, both held by tests: it never infers a
gate's state by parsing the English in a reason (it reads the `outcome` the
engine now carries), and it never writes portal text as markup.

**Two bugs found by looking at the page.**

1. **A euro threshold was being compared to lei.** The extractor read
   "Garanția de participare este de 4.500,00 euro" correctly as 4500 EUR, and
   the engine then compared the bare number against a profile figure in lei and
   printed "the buyer asks for 4.500 RON". Two faults in one line: a false claim
   about the buyer's own sentence, and a comparison about five times too
   lenient, which could let a tender pass a gate it was never measured against.
   A requirement in any currency other than RON is now CHECK, the reason names
   the real currency, and the headroom term no longer divides lei by euro.
   Fixed in its own commit, with six tests.
2. **A gate's state could only be recovered by reading English prose.**
   `Reason` now carries `outcome` — pass, fail, unknown or absent — straight
   from the engine. `bidscout explain` marks each line with it too.

**105 tests before, 123 after. `ruff` clean.** No existing test was changed or
weakened. `make demo` and `make check` both still run end to end.

Could not do, and why:

- **No live check of anything**, a fourth time. Nothing in this session touched
  the portal. The page shows the captured fixtures scored against
  `profile.example.yaml`, and says so on its face.
- **The page shows no GO**, because the example company does not clear any of
  the three fixtures. Rather than invent a tender to manufacture a green badge,
  the demo gained the third *already labelled* case from `eval/cases/`, which is
  what surfaced the euro bug. A real GO arrives with real data.
- **Secondary CPV codes**, still blocked on one live look (see step 3).

Next session starts at **immediate step 1** (live re-verify, Gabriel's machine).
After that, **step 4** — `bidscout fetch` — is what turns the page from a demo
into a thing worth opening every morning, because it is what stops the database
filling with notices the scorer skips.

### Session 7 — 2 October 2026 (cloud, no portal)

Step 1 was skipped again: it needs the live portal and this run was in the
cloud, where `e-licitatie.ro` is blocked at the gateway. Step 2's follow-up
(label thirty real notices) and step 3's remaining bullet (secondary CPV codes)
are blocked for the same reason. So this session took **step 4**, the first one
that can be built honestly offline.

**`bidscout fetch`** (`src/bidscout/fetch.py`) is the step between `watch` and
`score`. `watch` stores what the search results carry, and the search results
carry no requirements at all — so the scorer skipped every notice `watch` had
ever stored, correctly, and a database full of notices answered nothing. `fetch`
takes every stored notice with no Section 3, newest first, reads the section and
the file list, and stores both. `--limit` bounds one run (default 50, `0` for
all).

`Store.notices_missing_section3` is the queue. Unfiltered it is the complement
of what an unfiltered `score_stored` skips and counts, and a test asserts the
two agree on the same database. (They do diverge under `score --cpv`, which
walks only the filtered set — the agreement claim is about the unfiltered case.)

**The bug this nearly shipped with, and how it was caught.**

The first version of `fetch` refused to store a Section 3 that came back
carrying no text, on the reasoning that an empty section in the database reads
as a buyer who asks for nothing: every gate absent, nothing unresolved, score
over the threshold, verdict **GO** on a notice nobody read. That reasoning is
right. The guard was in the wrong place, and a review pass found three holes in
it before the patch was packaged:

1. The guard was a **list of Section 3 field names**, and it was wider than the
   list the extractor actually reads. A payload whose only prose sat in
   `efCriteriaBold1` — by its name, exactly where a bold financial criterion
   goes — passed the guard, was stored, and then scored **GO, 70**, on a notice
   where the buyer had written a 2.700.000 Lei turnover requirement. The guard
   defended the case it was written for and not the case that matters.
2. A notice whose section came back thin was **re-requested on every future
   run**, for ever, because nothing was written and it never left the queue —
   an unbounded repeat against somebody else's server, which is the very thing
   this module's docstring says it refuses to do.
3. `bidscout capture <id> --live` stores whatever the portal returns with no
   guard at all, so the same empty payload could reach the database by another
   door. A guard in `fetch` could never have been the whole story.

**The fix moved the guard to where it belongs.** `decide` now returns CHECK when
it recognised *no* requirements at all in a section, with a reason that says so
and sends the reader to the section itself. That is ground rule 2 applied in the
one module that exists to apply it, and it holds for any payload shape and any
command that stored it — `fetch`, `capture --live`, or a hand-written row.
`fetch` then does the simpler and more correct thing: it stores what arrived,
exactly as it arrived (ground rule 3), the notice leaves the queue, and a later
parser fix is replayed from the row instead of the notice having been discarded.
`has_section3_text` and its field list are gone.

Three smaller faults found in the same pass and fixed:

- **Simplified notices never left the queue and consumed `--limit`.** They can't
  be fetched — no detail endpoint is known — so with 60% of the market
  simplified, `bidscout fetch` could print "0 of 50" for ever while never
  reaching a readable notice. They are now excluded in SQL, before the `LIMIT`,
  and reported as a backlog figure instead.
- **`--limit 0` would have read nothing.** It is documented as "every notice",
  but passed straight through it becomes `LIMIT 0`: zero rows, and "Nothing to
  fetch" printed on a database full of unread notices. It is translated to "no
  limit" in `fetch_limit`, which is tested directly; a negative limit is now
  refused by the store, because SQLite reads one as no limit at all.
- **A file-list field of the wrong shape aborted the run.** Every field out of
  the portal is forced to a string; `noticeDocumentCode` was not, so a code
  arriving as an object reached SQLite and raised after the section had already
  been stored.

**Three tests were rewritten because they passed for the wrong reason.** One
asserted that argparse returns the number it was given rather than that the
limit translation works. One claimed to prove `fetch` opens no socket when
there is nothing to do, but would still have passed with the client built first
— and on Gabriel's machine, where the portal is reachable, that regression would
have made `pytest` itself call e-licitatie.ro; `_make_client` is now a seam the
test asserts against. One asserted a field-list relation in the harmless
direction only. A fourth, `test_fetch_is_not_listed_as_an_offline_command`, was
deleted outright: `OFFLINE_COMMANDS` in `cli.py` is read by nothing in `src/`,
so the test could only ever fail if somebody edited a dead constant.

**Every new test was then checked by breaking the behaviour it defends.** Seven
mutations — the engine guard removed, the simplified filter made a no-op, the
limit translation removed, the client built too early, the string coercion
dropped, the thin-payload refusal restored, the document groups hard-coded back
to five — and each one was caught by exactly the test named after it, and by no
others. The first attempt at this check was itself wrong: the mutations ran in a
copied directory whose venv still pointed its editable install at the original
source, so all 163 tests passed seven times in a row and proved nothing.

**123 tests before, 163 after. `ruff` clean.** No existing test was changed or
weakened. `make demo`, `make site` and `make check` all still run end to end.

Could not do, and why:

- **No live check of anything**, a fifth time. Nothing in this session touched
  the portal. Every call in `sicap/client.py` — including the two `fetch` now
  depends on, `GetSection3View` and `GetDfNoticeSectionFiles` — is still only as
  good as the 20 September spike notes.
- **Whether the section endpoint wants `noticeId` or `cNoticeId`** is still
  unconfirmed. `fetch` makes the same choice `capture` does — prefer the stored
  init id, fall back to the notice id — so if it is wrong, it is wrong in one
  documented place and in both commands at once.
- **The fetching branch of `bidscout fetch` is only tested against a fake.**
  There is no way around that here; the first real exercise is on your machine.
- **`docs/data.json` was deliberately left alone.** `make site` regenerates it
  with a new timestamp and no content change; committing that would be churn.

Found and not fixed (small, and not this item's job):

- `OFFLINE_COMMANDS` in `src/bidscout/cli.py` is referenced nowhere. The split
  between commands that need the portal and commands that do not is enforced by
  hand in `--help` and in the docs tables. Either wire it up or delete it.

---

### Session 7b — 2 October 2026 (Gabriel's machine, portal reachable)

The patch applied cleanly. **163 tests pass, `ruff` clean, on Windows.** Then the
first live run in the project's history, and it stopped at the first request.

**`bidscout watch --days 1` → HTTP 403 Forbidden** on
`POST /api-pub/NoticeCommon/GetCNoticeList/`. Not a moved field, not a bad
filter: the portal refused the request outright.

**The likely cause is a gap in the written record, not in the code.** Session 1
(20 September) found *three* traps: a required header, a filter the server
ignores, and a cap that looks like a count. The rebuild carried two of them into
`filters.py` and `_refuse_capped_result`. **The required header was never
re-implemented**, because session 1's code was lost and
`docs/data-sources.md` never recorded which header it was — it only says the
API was called "from the browser, same origin". That is the one trap with no
test, and it is the one that fired.

Not yet known, and the next thing to establish: whether the portal refuses
*our* User-Agent specifically, refuses non-browser clients generally, or has
closed the public API altogether. Those are three different problems with three
different answers, and the third would mean rewriting section 2 of
`docs/data-sources.md` rather than patching the client.

**`fetch` and `score` were not reached.** `fetch` correctly made no request
(empty database). `score` stopped because there is no `profile.yaml` on the
machine yet — Gabriel's own file, four real figures, still to be filled in.

**One small bug found by running it.** On an **empty** database `fetch` prints
"every stored notice that can be read already has its Section 3", which is true
of zero notices and useless to read. It should say the database holds no
notices. Not yet fixed.

---

## Where we are at (end of session 7)

The offline half of this project is finished and measured: 163 tests, `ruff`
clean, a static page, an accuracy harness, and now a complete ingest path —
`watch` finds notices, `fetch` reads them, `score` ranks them, `export`
publishes them. Every one of those four runs from the database or a fixture.

One real defect class was closed this session, and it was not in the new
feature: a stored Section 3 that the reader could not understand used to score
GO. That was reachable before today by `capture --live` and by any hand-written
row; `fetch` would simply have made it common. It is now CHECK.

The live half has now been tried once, and it got a **403 on the first
request**. Nothing downstream of that — field names, Section 3 shapes, the
`noticeId` vs `cNoticeId` question — has been tested at all, and none of it can
be until the portal answers. Everything in `sicap/client.py` is still only as
good as the 20 September spike notes.

## Next actions in the next task

1. **Diagnose the 403.** Everything else waits on this. Establish which of the
   three it is — our User-Agent, non-browser clients in general, or the public
   API being gone — then record the answer in `docs/data-sources.md` whatever it
   turns out to be. If a header is needed, it gets a test; if the portal is
   deliberately refusing tools, that is a decision to take knowingly and write
   down, not to work around quietly.
2. **Fill in `profile.yaml`** from `profile.example.yaml`: average turnover over
   three financial years, largest evidenced similar contract, cash available for
   a participation guarantee, contract-size range. Every verdict is measured
   against these four numbers.
3. **Then the rest of immediate step 1:** `watch` → `fetch` → `score`, confirm
   whether `GetSection3View` wants `noticeId` or `cNoticeId`, and whether
   `GetDfNoticeSectionFiles` still returns the five groups. Watch for notices
   that come back CHECK with "recognised none of the qualification criteria":
   each is a moved field name or a gate the extractor needs to learn.
4. **Fix the empty-database message in `fetch`** (see session 7b).
5. **Then, still live:** `bidscout capture <id> --live` on about thirty notices
   and label them, so the "60% coverage" figure becomes a measurement instead of
   a guess (immediate step 2's follow-up).
6. **Then, with one live look at a notice that has one:** store secondary CPV
   codes (immediate step 3's remaining bullet), and read the lot contents via
   `GetSection22LotList`.
7. **Offline, if a cloud session comes first:** immediate step 5, direct
   purchases — mapped in `docs/data-sources.md` section 2.5, no Section 3 to
   read, so the gates differ and it needs its own short rule set.
