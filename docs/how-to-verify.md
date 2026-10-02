# bidscout — how to check my work yourself

Rule for this project: **anything Claude checks, Gabriel must be able to
check.** No finding lives only in a chat window. Every claim gets a command.

## Set up

```bash
make install
make check      # 163 offline tests + ruff
make demo       # the whole pipeline on captured fixtures, no network
```

## The commands that reproduce every claim

| Command | Claim it tests | Needs the portal |
|---|---|---|
| `make test` | 163 offline tests on captured fixtures. Under a second. | no |
| `make lint` | `ruff` clean at line length 100. | no |
| `make demo` | Store → extract → decide → rank, end to end. | no |
| `bidscout score` | Ranking from the database only. | no |
| `bidscout explain <id>` | Every reason carries the buyer's own sentence. | no |
| `bidscout requirements <id>` | The stored trace: every figure with its quote and field. | no |
| `make site` | The published page is rebuilt from the database, not hand-written. | no |
| `make serve` | The page as GitHub Pages serves it, at localhost:8000. | no |
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
- No amount in `docs/data.json` is a JSON number, so no figure on the page
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
- The accuracy harness counts nothing nobody labelled, and reports an
  invented figure separately from a missed one.

**Not proven, because the cloud cannot reach e-licitatie.ro:**

- That the endpoints in `docs/data-sources.md` still exist and still answer.
- That the field names in Section 3 are unchanged.
- The 60% coverage figure, the volume table, and every other number measured
  during the 20 September spike. `make eval` now measures coverage, but on
  three labelled notices only — two transcribed from the spike and one
  written by hand. Three cases is a smoke test, not a measurement. Capture
  thirty and the number starts meaning something.

Run `bidscout watch --days 1 && bidscout fetch && bidscout score` on your own
machine to close that gap. If a field has moved, fix `docs/data-sources.md` in
the same commit as the code. Two things to confirm while you are there: whether
`GetSection3View` wants `noticeId` or `cNoticeId` (`fetch` prefers the stored
`noticeId` and falls back), and whether `GetDfNoticeSectionFiles` still returns
the five groups it returned in September.

## Note for future sessions

The cloud sandbox cannot reach `e-licitatie.ro` (egress blocked at the
gateway). Live checks run on Gabriel's machine. Offline tests and parser work
can be done in the sandbox against `tests/fixtures/`.
