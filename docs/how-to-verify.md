# bidscout — how to check my work yourself

Rule for this project: **anything Claude checks, Gabriel must be able to
check.** No finding lives only in a chat window. Every claim gets a command.

## Set up

```bash
make install
make check      # 185 offline tests + ruff
make demo       # the whole pipeline on captured fixtures, no network
```

## The commands that reproduce every claim

| Command | Claim it tests | Needs the portal |
|---|---|---|
| `make test` | 185 offline tests on captured fixtures. About 40 s; the warehouse tests run the real `dbt build`. | no |
| `make lint` | `ruff` clean at line length 100. | no |
| `make demo` | Store → extract → decide → rank, end to end. | no |
| `bidscout score` | Ranking from the database only. | no |
| `bidscout explain <id>` | Every reason carries the buyer's own sentence. | no |
| `bidscout requirements <id>` | The stored trace: every figure with its quote and field. | no |
| `bidscout transform` | The warehouse builds from landing and all its data tests pass. | no |
| `make site` | score → `dbt build` → `site/data.json` from the app marts, from the live database. | no |
| `make demo-site` | The same, from the captured fixtures. | no |
| `make serve` | The page as GitHub Pages serves it, at localhost:8000. | no |
| `make docs` | The warehouse's models, columns, tests and lineage graph, in a browser. | no |
| `bidscout stats` | What the database holds. | no |
| `make eval` | Coverage and precision per gate, on hand-labelled notices. | no |
| `bidscout capture <id>` | A stored Section 3 becomes a new case to label. | no |
| `bidscout watch --days 1` | The portal still answers as documented. | **yes** |
| `bidscout fetch` | A stored notice's Section 3 and file list are read and stored. | **yes** |
| `bidscout fetch` on a read database | "Nothing to fetch", and no client is built. | no |

## What is proven and what is not (2 October 2026)

**Proven by the test suite, offline:**

- An unknown or known-ignored filter name is refused before a request is sent.
- A capped search raises instead of being read as a count.
- A `null` notice view raises instead of reaching the parser.
- Romanian amounts are read correctly, and bare years are not read as money.
- A requirement cannot exist without a quote.
- An unreadable requirement or a missing profile figure gives CHECK, not NO-GO.
- A tender split into lots gives CHECK, not NO-GO, because the notice-level
  figure may be the total for all lots and the lots have not been read.
- A stored requirement amount comes back as the Decimal the buyer wrote,
  not as a float.
- A database written before the `has_lots` column still opens, and its rows
  are kept rather than rebuilt.
- A requirement the buyer stated in euro gives CHECK, and the reason names
  EUR rather than claiming RON.
- No amount in `site/data.json` is a JSON number, so no figure on the page
  has passed through a float.
- The page reads the schema version the exporter writes, and never puts
  portal text into the DOM as markup.
- A notice with no stored Section 3 is skipped and counted, not scored.
- A stored Section 3 the reader recognised **nothing** in gives CHECK, never
  GO. One test puts a 2.700.000 Lei turnover rule in a Section 3 field no gate
  maps to, stores it, and asserts the verdict is CHECK — because with no
  requirements read, every gate would otherwise say "the buyer does not ask for
  one" and the score alone would decide.
- The fetch queue and the notices an unfiltered `score` skips are the same
  list; a test asserts they agree. (Under `score --cpv` they diverge, because
  the scorer then walks only the filtered set.)
- Simplified notices are left out of the fetch queue in SQL, so they cannot
  consume `--limit` and starve the notices that can be read.
- `--limit 0` reads every notice rather than none; a negative limit is refused
  rather than read by SQLite as no limit at all.
- A fetch run survives one notice the portal refuses, and keeps what it had
  already stored when something unexpected stops it.
- A notice already read, including one the portal answered thinly, is never
  asked for again.
- Every group in the file list is read, including one the portal has not sent
  before; an entry with no URL is counted rather than stored under an empty
  key, and a field of the wrong shape never reaches SQLite.
- A file list that fails to arrive does not unstore the Section 3 that did.
- Every one of the above was checked by breaking the behaviour and watching the
  named test fail. Seven mutations, seven catches, no false greens.
- The raw portal payload survives a database round trip.
- The portal's "not found" (HTTP 200, `hasError: true`) is raised, never stored
  as a Section 3; one already stored is put back in the fetch queue and never
  scored.
- A Section 3 field that arrives as a boolean reads as no text instead of
  crashing the scorer.
- Concession notices (type 7) stay out of the fetch queue, like simplified ones.
- The warehouse gives every landed notice exactly one row in
  `app.app_tenders`, with the stage it has reached; only a scored notice
  carries a decision (also a dbt data test, `scored_iff_decided`).
- One buyer stays one buyer however its CUI is written (`RO 4305814`,
  `4305814`).
- A broken contract — here, a decision outside GO / CHECK / NO-GO — fails
  `dbt build`, and the export stops instead of publishing it.
- The accuracy harness counts nothing nobody labelled, and reports an
  invented figure separately from a missed one.

**Proven live, on Gabriel's machine, 2 October 2026:**

- `watch --days 1` stored 129 notices (44 contract, 83 simplified, 2
  concession) once the `Referer` header was sent.
- `GetSection3View` and `GetDfNoticeSectionFiles` take the **cNoticeId** in
  their `initNoticeId` parameter. Asked with the `noticeId` they answer "not
  found" (Section 3) or a list of error strings (file list).
- `fetch` then read Section 3 for 44 of 44 contract notices and stored 301
  file-list rows, in the groups `dfNoticeDocs` and `duaeDocs`.
- `score` ranked all 44; `make site` published them.

**Still not proven:**

- The 60% coverage figure. `make eval` measures coverage, but on three
  labelled notices only. Capture thirty real ones and label them.
- An endpoint for simplified (SCN) and concession (PC) notices — 85 of the 129.
- Where a secondary CPV code lives.

## Note for future sessions

The cloud sandbox cannot reach `e-licitatie.ro` (egress blocked at the
gateway). Live checks run on Gabriel's machine, which can. Offline tests and parser work
can be done in the sandbox against `tests/fixtures/`.
