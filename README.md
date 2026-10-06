# bidscout

**A bid agent for Romanian public tenders (SEAP / SICAP).**

It reads each new tender, compares it with your company profile, and answers
one question: *should you bid?*

*Not technical? Start with the plain-language overview: [OVERVIEW.md](OVERVIEW.md).*

**The page:** <https://gabrieln2805.github.io/bidscout/> — real tenders from the
public SICAP API, scored against an example company. Every number on it comes
out of the warehouse tables described below, by one command.

---

## Where the data comes from

```
SICAP public JSON API          e-licitatie.ro/api-pub — public, no sign-in
   │  bidscout watch / fetch
   ▼
landing    data/bidscout.sqlite3   the portal's JSON exactly as it arrived
   │  bidscout score               + the rules engine's verdicts
   ▼
warehouse  data/bidscout.duckdb    dbt: staging → core marts → app marts
   │  bidscout export
   ▼
site/data.json  →  site/index.html  the page reads the app_* marts only
```

- **What the portal is and how we call it:** `docs/data-sources.md`
- **Every table, its grain, and which ones the app reads:** `docs/data-model.md`
- **See the tables themselves:** `make explore` — DuckDB's web UI on the warehouse

## Try it

```bash
make install
make demo-site     # the whole road on captured fixtures, no network
make serve         # http://localhost:8000
```

With the portal reachable, use real data:

```bash
make ingest        # land yesterday's notices and read their Section 3
make site          # score → dbt build → site/data.json
```

Then make it yours:

```bash
cp config/profile.example.yaml config/profile.yaml   # your own numbers
bidscout score
bidscout explain <c_notice_id>
```

No `make`? Every target is one `bidscout` command — see the `Makefile`.

## The problem

A Romanian company that sells to the state loses two or three days on every
tender file, and most of that work happens before anybody decides to bid:
read 30 to 80 pages of PDF to find the qualification criteria, compare them
with your turnover and your past contracts, list the documents and the
deadlines, then fill the DUAE.

Monitor tools exist. They tell you that a tender appeared. They do not tell
you whether you qualify.

## What bidscout does today

1. **Watches** SEAP and lands every new notice, raw.
2. **Reads** the qualification section (Section 3) and the file list out of the
   portal's own JSON. On the first live run, 44 of 44 contract notices were
   read. Simplified and concession notices — 85 of 129 that day — have no known
   endpoint yet and are listed as unread, never scored.
3. **Extracts** the gates as facts that each keep the buyer's own sentence.
4. **Decides** GO, CHECK or NO-GO with a score out of 100 and a short reason:

   > **NO-GO.** annual turnover: the buyer asks for 2.700.000 RON;
   > you have 1.200.000 RON.
   > Source: `efCriteriaMin`.

5. **Models** it all into a dbt warehouse: buyers, CPV codes, notices,
   documents, requirements, verdicts — tested on every build.
6. **Shows its work.** One static page, written from the app marts: your company
   on the left, the tenders ranked on the right, click one for the buyer's own
   sentences, and the notices not read listed with the reason.
7. **Measures itself.** `bidscout eval` scores the extractor against notices
   labelled by hand. Three so far — a smoke test, not yet a measurement.

Not built yet: direct acquisitions, simplified notices, the document checklist,
alerts, and PDF reading. See `STATUS.md`.

## How it decides

A plain rules engine makes the decision. The rules live in
`config/rules/it.yaml`, not in code, so every verdict can be explained, tested,
and corrected by a person who does not write Python.

```
hard gates  -> a failure = NO-GO, but only when both numbers are known
weights     -> a score from 0 to 100 for everything else
```

A missing fact or an unreadable requirement produces **CHECK**, never NO-GO
(`tests/test_unknown_never_becomes_no_go.py`). A tender split into lots is held
at CHECK for the same reason. The warehouse holds the same line at its edge: a
decision appears only on a notice that was read and scored (the dbt test
`scored_iff_decided`).

## Commands

| Command | What it does | Needs the portal |
|---|---|---|
| `bidscout watch --days 1` | Land new notices | **yes** |
| `bidscout fetch` | Read Section 3 and the file list for landed notices | **yes** |
| `bidscout score` | Rank landed tenders | no |
| `bidscout transform` | Build the dbt warehouse from landing | no |
| `bidscout explore` | Browse every table in DuckDB's web UI, read-only (`make explore`) | no |
| `bidscout export` | score → transform → `site/data.json` from the app marts | no |
| `bidscout explain <id>` | Every reason behind one verdict, with quotes | no |
| `bidscout requirements <id>` | The sentences the last score read, with their field | no |
| `bidscout stats` | What landing holds | no |
| `bidscout eval` | Measure the extractor against the labelled cases | no |
| `bidscout capture <id> [--live]` | Turn a Section 3 into a new case to label | `--live` only |
| `make check` | 186 offline tests + `ruff` | no |
| `make docs` | Browse the warehouse models and lineage (dbt docs) | no |

## Layout

```
src/bidscout/        Python: ingest, extract, decide, export
  sicap/               the only place that knows a SEAP URL
  fetch.py             reads the Section 3 and file list that watch cannot
  extract/             portal text -> facts that keep their quote
  decide/              the rules engine
  store/               landing (SQLite); the raw JSON is never dropped
  pipeline.py          portal item -> notice; the offline scorer
  warehouse.py         runs dbt, reads the app marts
  export.py            app marts -> site/data.json
  accuracy/            the eval harness
warehouse/           the dbt project: staging, intermediate, core, app
site/                the published page: index.html + data.json
config/              rules/it.yaml and profile.example.yaml
docs/                data-sources, data-model, publishing, how-to-verify, history
eval/cases/          notices labelled by hand
tests/               offline tests and captured fixtures
data/                landing and warehouse files (not committed)
```

## Limits

bidscout is a decision aid. It is not legal advice, and it does not submit
anything for you. You read the file, you approve it, you send it.
