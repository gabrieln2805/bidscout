# bidscout — status

**Update this file at the end of every session.** It is the first thing to
read when picking the project up. What happened in each session is in
`docs/history.md`.

Last updated: **6 October 2026**, session 9.

---

## What this is

A tool that watches Romanian public tenders (SEAP / SICAP), reads each new one,
compares it against a company, and answers one question: **should you bid?**

**The goal: a solid portfolio project.** Something a client or employer can
open, understand in a minute, and trust after five: a live page on real public
data, an honest data pipeline from the portal to the page, and measured
accuracy rather than claims.

**Not a business, by decision (6 October 2026).** A market sweep found about
19 Romanian products in the space, at least seven of which already score
tenders against a company profile (DataDriven, Licitor, SEAP Match, Licitații
Rapide, SEAP Navigator, eLicit, licitatie-publica.ro), most for under €50 a
month, plus well-funded players abroad. The full analysis is in
`strategy/market-proposal.md`; keep it out of the public repository. So: no
pricing, no pilots, no sales features. Every next step is judged by one
question: *does it make the project more impressive or more trustworthy to
someone reading it?*

---

## Where we stand

The whole pipeline runs on **real data**, and the page is **live**:
<https://gabrieln2805.github.io/bidscout/>

```
SICAP API --watch/fetch--> landing (SQLite) --score--> --dbt build--> warehouse (DuckDB)
          --export--> site/data.json --> site/index.html (GitHub Pages)
```

The page shows the 2 October run: 129 notices, **44 of 44 contract notices
read and scored** (1 GO, 32 CHECK, 11 NO-GO against the example company), 85
simplified and concession notices listed as not read. It does not refresh on
its own yet.

| Piece | State | Portfolio value |
|---|---|---|
| Talking to SEAP | Working live: search, Section 3, file list | Shows reverse-engineering an undocumented public API, traps written down as tests |
| Reading the requirements | Working on real Section 3s, with quotes | Core of the project |
| Deciding GO / CHECK / NO-GO | Working, 3 gates + a score, rules in YAML | Explainable, testable decisions |
| Data model | dbt warehouse, staging → core → app tables, 52 data tests | Shows modern data engineering |
| Browsing the data | `make explore` (DuckDB UI), `make docs` (dbt docs) | |
| The page | **Live on GitHub Pages**, reads the app tables only | The thing people open |
| Tests | 187 offline tests, `ruff` clean | No CI yet, so nobody sees them pass |
| Measuring accuracy | Harness works; only 3 labelled notices | The biggest credibility gap |
| Out-of-sector GOs | **A security-guard tender shows GO 75 for an IT company** | A visible flaw on the live page |
| Daily refresh | Not started | Without it, the "live" page is a snapshot |
| Simplified notices (~64% of volume) | Listed, not read; endpoint unknown | |
| AI layer | Designed, not built | High portfolio value if done carefully |
| Docs | README (technical), OVERVIEW (plain language), data model, data sources | |

---

## Next steps, in order

Ordered by what a reader of the project notices first.

1. **Fix the wrong-sector GO.** A tender outside the profile's `cpv_watchlist`
   can be CHECK at most, with a reason that says why. One rule, one test, one
   re-export. The first tender on the live page should not be a mistake.
2. **CI on GitHub.** A workflow that runs the tests, `ruff` and `dbt build` on
   the demo fixtures on every push, with a badge in the README. It costs an
   hour and makes the 187 tests visible to anyone.
3. **Keep the page fresh.** First try `watch`/`fetch` from a GitHub Actions
   runner (one manual run answers whether it can reach the portal). If it can,
   a daily scheduled workflow refreshes `site/data.json` and commits it. If it
   cannot, a Windows Task Scheduler job on this machine does the same.
4. **Measure accuracy and show it.** Label 30 real notices with
   `bidscout capture <id>`, then put the `bidscout eval` table in the README
   and on the page: coverage, precision, invented figures. Very few projects
   in this space publish an error rate; this one can.
5. **The AI layer, done the careful way.** Claude reads the Section 3s the
   rules could not read, returns figures with quotes, and code checks that each
   quote appears word for word before the rules engine uses it. Measured with
   the same eval as step 4, before and after. Shows LLM engineering with
   guardrails, the strongest portfolio piece left.
6. **Write the case study.** A short article (and a one-minute screen
   recording): the problem, the portal's traps, the data model, how a verdict
   is traced to a sentence, the measured accuracy. Publish the dbt docs next to
   the page. This is what gets sent to a client.
7. **Simplified notices.** Find the endpoint (open an SCN page on
   e-licitatie.ro with the browser's dev tools). Doubles the coverage, but only
   matters once steps 1–6 are done.

**Parked, not planned:** pricing, pilot users, alerts by email, consultant
workspace, DUAE pre-fill, consortium matching, direct purchases, EU tenders.
They were business features; the project does not need them to be good.

---

## Open questions

- Can a GitHub-hosted runner reach `e-licitatie.ro`? (Decides step 3.)
- The detail endpoint for simplified (type 17) and concession (type 7) notices.
- Where a notice's secondary CPV codes live.

---

## Ground rules

1. **Anything Claude checks, Gabriel must be able to check.** Every finding
   becomes a command or a test in the repo, not a claim in a document.
2. **Never say "you do not qualify" when the honest answer is "we could not
   tell".** A missing fact or an unreadable sentence produces CHECK.
3. **Keep the raw data for ever.** `notices.raw` and `sections.section3_raw`
   are never dropped. A parser rewrite is replayed from disk.
4. **The repository is the project.** Work that is not written to
   `D:\DS ML\bidscout` does not exist. Save and push at the end of a session.
