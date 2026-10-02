# bidscout — status

**Update this file at the end of every session.** It is the first thing to
read when picking the project up. What happened in each session is in
`docs/history.md`.

Last updated: **2 October 2026**, session 8.

---

## What this is

A tool that watches Romanian public tenders (SEAP / SICAP), reads each new one,
compares it against a company, and answers one question: **should you bid?**

**The target:** a public frontend connected to live public bid data. That means
a page anyone can open, showing today's tenders from the SICAP public API,
each ranked and explained against a company profile.

Two goals, in order:

1. A portfolio project good enough to win freelance work.
2. If it earns it, a paid tool for small companies and bid consultants.

---

## Where we stand

The whole road now runs on **real data**, once, by hand:

```
SICAP API --watch/fetch--> landing (SQLite) --score--> --dbt build--> warehouse (DuckDB)
          --export--> site/data.json --> site/index.html
```

On 2 October: 129 notices landed, **44 of 44 contract notices read and scored**
(1 GO, 32 CHECK, 11 NO-GO against the example company), 85 simplified and
concession notices listed as unread. All of it is in `site/data.json`.

| Piece | State | Checked how |
|---|---|---|
| Talking to SEAP | **Working live** — search, Section 3, file list | 2 Oct run; offline tests |
| Contract notices (CN) | **Working live**, 44 / 44 read | 2 Oct run |
| Simplified notices (SCN), ~64% of volume | Listed, not read — endpoint unknown | — |
| Concession notices (PC) | Listed, not read — refused by the CN endpoint | — |
| Direct purchases | Mapped, not wired in | — |
| Reading the requirements | Working on real Section 3s | 11 tests + live |
| Deciding GO / CHECK / NO-GO | Working, 3 gates + a score | 7 tests + live |
| Data model | **dbt warehouse**: staging → core → app marts | 52 dbt data tests on every build |
| The page | Working, reads the app marts only | export tests + headless render |
| Publishing | Workflow added; **needs the Pages source switched** | — |
| Running it on a schedule | Not started — every run is by hand | — |
| Measuring how well we read | Harness works, only 3 labelled notices | `make eval` |
| Reading the PDFs | Not started | — |

**185 automatic tests, all offline, all passing. `ruff` clean.**

Where to look: data sources in `docs/data-sources.md`, tables in
`docs/data-model.md`, how to check any claim in `docs/how-to-verify.md`.

---

## What the live data showed (2 October)

- **The id question is settled:** the detail endpoints take the `cNoticeId`.
  The `noticeId` gets an HTTP 200 "not found" that looks like data.
- **The CPV problem is real, and it shows on the page.** `watch` lands every
  sector, and the IT rule set ranks a *security-guard* tender (CN1096923)
  **GO 75**. Turnover, value and deadline add up to more than the threshold
  without any CPV match. For an IT company that is a wrong GO on a public page.
- **Most of the market is still unread.** 85 of 129 notices are simplified or
  concession notices.
- **Real files:** 301 attachments on 44 notices, mostly `.p7s` signature
  wrappers (155), then PDF (84) and the DUAE XML (43).

---

## Next steps, in order

1. **Stop out-of-sector GOs.** Either a notice outside the profile's
   `cpv_watchlist` cannot be GO (CHECK at most), or `watch` / the export filters
   to the watchlist. Decide which. Today the page shows a guard-services GO.
2. **Switch GitHub Pages to Actions and push.** Settings → Pages → Source:
   *GitHub Actions*. Until then the live URL keeps serving the old `/docs`
   setting, which no longer holds a page.
3. **Run it every day.** A scheduled job for `make ingest && make site`. The
   landing database is not committed, so it needs a home first: Gabriel's
   machine (Task Scheduler) is the only one known to reach the portal. Whether
   GitHub runners can reach `e-licitatie.ro` is untested.
4. **Simplified notices.** Find the detail endpoint (open the SCN page in the
   portal with dev tools). It is the largest gap in coverage.
5. **Label thirty real notices** with `bidscout capture <id>`, so the coverage
   figure is a measurement. The 44 now in landing are the material.
6. **Secondary CPV codes and lot contents.** Both need one live look at a notice
   that has them.
7. **Direct purchases**, then the document checklist, then alerts.

---

## Open questions

- The detail endpoint for simplified (type 17) and concession (type 7) notices.
- Direct purchases: the publication-date and CPV filter names.
- Where a notice's secondary CPV codes live.
- Two notice types not identified: `type 12`, and `RFD…`.
- Can a GitHub-hosted runner reach the portal?

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
