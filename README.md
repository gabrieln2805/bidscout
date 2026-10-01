# bidscout

**A bid agent for Romanian public tenders (SEAP / SICAP).**

It reads each new tender, compares it with your company profile, and answers
one question: *should you bid?*

**The page:** <https://gabrieln2805.github.io/bidscout/> — built by
`make site` from the captured fixtures, so every number on it is reproduced by
a command in this repository.

---

## Try it in one minute

```bash
make install
make demo
```

`make demo` builds a small database from captured fixtures and scores it. It
needs no network and no profile. You should see one NO-GO with both numbers
printed, one CHECK, and one notice skipped because it was never read in full.

And to see the page:

```bash
make site      # rebuild the demo database and the JSON the page reads
make serve     # http://localhost:8000
```

Then make it yours:

```bash
cp profile.example.yaml profile.yaml    # put your own numbers in
.venv/bin/bidscout --db data/demo.sqlite3 score
.venv/bin/bidscout --db data/demo.sqlite3 explain 1096282
```

## The problem

A Romanian company that sells to the state loses two or three days on every
tender file, and most of that work happens before anybody decides to bid:
read 30 to 80 pages of PDF to find the qualification criteria, compare them
with your turnover and your past contracts, list the documents and the
deadlines, then fill the DUAE.

Monitor tools exist. They tell you that a tender appeared. They do not tell
you whether you qualify.

## What bidscout does today

1. **Watches** SEAP for tenders in your CPV codes and stores what is new.
2. **Reads** the qualification section out of the portal's own JSON. About
   60% of tenders can be decided without opening a PDF.
3. **Extracts** the gates as facts that each keep the buyer's own sentence.
4. **Decides** GO, CHECK or NO-GO with a score out of 100 and a short reason:

   > **NO-GO.** annual turnover: the buyer asks for 2.700.000 RON;
   > you have 1.200.000 RON.
   > Source: `efCriteriaMin`.

5. **Measures itself.** `bidscout eval` reads a set of notices a person has
   labelled by hand and prints, per gate, how often the extractor finds a
   figure at all and how often the figure is right. The "60%" above is a
   guess from a one-day spike until that table says otherwise.

6. **Shows its work.** One static page — your company on the left, the
   tenders ranked on the right, click one for the buyer's own sentences. It is
   written by `bidscout export` from the scored database, so it can never
   claim anything the database does not hold. See `docs/README.md`.

Not built yet: direct acquisitions, the document checklist, alerts, and PDF
reading for the other 40%. See `STATUS.md`.

## How it decides

A plain rules engine makes the decision. The rules live in `rules/it.yaml`,
not in code, so every verdict can be explained, tested, and corrected by a
person who does not write Python.

```
hard gates  -> a failure = NO-GO, but only when both numbers are known
weights     -> a score from 0 to 100 for everything else
```

A missing fact or an unreadable requirement produces **CHECK**, never NO-GO.
That rule is held in place by `tests/test_unknown_never_becomes_no_go.py`. A
tender split into lots is held at CHECK for the same reason: the notice-level
figure may be the total for every lot, and bidscout has not read the lots yet
(`tests/test_a_multi_lot_tender_is_never_a_no_go.py`).

Every figure the extractor reads is written to a `requirements` table with the
buyer's sentence and the field it came from, so a verdict can be traced back
without re-running the parser: `bidscout requirements <id>`. That table is
derived — the stored raw Section 3 stays the only source of truth, and the
scorer re-reads it on every run.

## Commands

| Command | What it does | Needs the portal |
|---|---|---|
| `bidscout score` | Rank stored tenders | no |
| `bidscout explain <id>` | Every reason behind one verdict, with quotes | no |
| `bidscout requirements <id>` | The sentences the last score read, with their field | no |
| `bidscout export` | Write `docs/data.json`, the file the web page reads | no |
| `bidscout stats` | What the database holds | no |
| `bidscout eval` | Measure the extractor against the labelled cases | no |
| `bidscout capture <id>` | Turn a stored Section 3 into a new case to label | no |
| `bidscout watch --days 1` | Poll the portal and store what is new | **yes** |
| `bidscout capture <id> --live` | Fetch a Section 3 and capture it | **yes** |
| `make site` | Rebuild the demo database and the page's data | no |
| `make serve` | Serve `docs/` the way GitHub Pages does | no |
| `make test` | 123 offline tests | no |
| `make lint` | `ruff`, line length 100 | no |

## Layout

```
src/bidscout/
  sicap/      the only place that knows a SEAP URL
  extract/    portal text -> facts that keep their quote
  decide/     the rules engine; the rules are YAML
  store/      SQLite; the raw JSON is never dropped
  pipeline.py the glue, and the offline scorer
  export.py   the scored database -> the JSON the web page reads
  cli.py      the commands
  accuracy/   the harness: labelled cases in, a coverage table out
rules/it.yaml the IT rule set
eval/cases/   notices labelled by hand; the input `bidscout eval` measures
docs/         the published page (index.html + data.json), and the
              verified findings about the portal
```

## Data

Public data only: the SICAP public JSON API behind `e-licitatie.ro`. No
sign-in, no scraping behind a login, no paywall. Every endpoint, field and
limit is written down in `docs/data-sources.md`.

## Limits

bidscout is a decision aid. It is not legal advice, and it does not submit
anything for you. You read the file, you approve it, you send it.
