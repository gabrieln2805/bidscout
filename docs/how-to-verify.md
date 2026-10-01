# bidscout — how to check my work yourself

Rule for this project: **anything Claude checks, Gabriel must be able to
check.** No finding lives only in a chat window. Every claim gets a command.

## Set up

```bash
make install
make check      # 123 offline tests + ruff
make demo       # the whole pipeline on captured fixtures, no network
```

## The commands that reproduce every claim

| Command | Claim it tests | Needs the portal |
|---|---|---|
| `make test` | 123 offline tests on captured fixtures. Under a second. | no |
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

## What is proven and what is not (1 October 2026)

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

Run `bidscout watch --days 1` on your own machine to close that gap. If a
field has moved, fix `docs/data-sources.md` in the same commit as the code.

## Note for future sessions

The cloud sandbox cannot reach `e-licitatie.ro` (egress blocked at the
gateway). Live checks run on Gabriel's machine. Offline tests and parser work
can be done in the sandbox against `tests/fixtures/`.
