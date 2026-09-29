# bidscout — how to check my work yourself

Rule for this project: **anything Claude checks, Gabriel must be able to
check.** No finding lives only in a chat window. Every claim gets a command.

## Set up

```bash
make install
make check      # 65 offline tests + ruff
make demo       # the whole pipeline on captured fixtures, no network
```

## The commands that reproduce every claim

| Command | Claim it tests | Needs the portal |
|---|---|---|
| `make test` | 65 offline tests on captured fixtures. Under a second. | no |
| `make lint` | `ruff` clean at line length 100. | no |
| `make demo` | Store → extract → decide → rank, end to end. | no |
| `bidscout score` | Ranking from the database only. | no |
| `bidscout explain <id>` | Every reason carries the buyer's own sentence. | no |
| `bidscout stats` | What the database holds. | no |
| `bidscout watch --days 1` | The portal still answers as documented. | **yes** |

## What is proven and what is not (27 September 2026)

**Proven by the test suite, offline:**

- An unknown or known-ignored filter name is refused before a request is sent.
- A capped search raises instead of being read as a count.
- A `null` notice view raises instead of reaching the parser.
- Romanian amounts are read correctly, and bare years are not read as money.
- A requirement cannot exist without a quote.
- An unreadable requirement or a missing profile figure gives CHECK, not NO-GO.
- A notice with no stored Section 3 is skipped and counted, not scored.
- The raw portal payload survives a database round trip.

**Not proven, because the cloud cannot reach e-licitatie.ro:**

- That the endpoints in `docs/data-sources.md` still exist and still answer.
- That the field names in Section 3 are unchanged.
- The 60% coverage figure, the volume table, and every other number measured
  during the 20 September spike.

Run `bidscout watch --days 1` on your own machine to close that gap. If a
field has moved, fix `docs/data-sources.md` in the same commit as the code.

## Note for future sessions

The cloud sandbox cannot reach `e-licitatie.ro` (egress blocked at the
gateway). Live checks run on Gabriel's machine. Offline tests and parser work
can be done in the sandbox against `tests/fixtures/`.
