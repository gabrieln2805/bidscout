"""The command line.

Every claim this project makes has a command here that re-proves it. The
commands split cleanly in two: those that need the portal, and those that do
not. ``score``, ``stats`` and ``explain`` run entirely from the database, so
they work on a machine with no access to e-licitatie.ro.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from bidscout import __version__
from bidscout.accuracy.cases import DEFAULT_CASE_DIR
from bidscout.decide.rules import RuleSet, load_profile, load_rules
from bidscout.errors import SectionNotStored
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import DEFAULT_DB_PATH, Store

#: Commands that never open a socket. ``capture`` is offline too unless it is
#: given ``--live``, so it is not in this set.
OFFLINE_COMMANDS = frozenset(
    {"score", "stats", "explain", "requirements", "eval", "export"}
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bidscout", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"bidscout {__version__}")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="path to the SQLite file")
    parser.add_argument("--profile", default="profile.yaml", help="your company profile")
    parser.add_argument("--rules", default="rules/it.yaml", help="the rule set to apply")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="rank stored tenders (no request to SEAP)")
    score.add_argument("--cpv", help="primary CPV prefix, e.g. 72000000")
    score.add_argument("--limit", type=int, default=20)
    score.add_argument(
        "--live", action="store_true", help="fetch from SEAP first (needs network access)"
    )

    explain = sub.add_parser("explain", help="show every reason behind one verdict")
    explain.add_argument("c_notice_id")

    requirements = sub.add_parser(
        "requirements",
        help="show the sentences the last score read for one notice (no request to SEAP)",
    )
    requirements.add_argument("c_notice_id")

    export = sub.add_parser(
        "export",
        help="write the scored database to a JSON file for the web page (no request to SEAP)",
    )
    export.add_argument(
        "--out", default="docs/data.json", help="where to write the file the page reads"
    )
    export.add_argument("--cpv", help="primary CPV prefix, e.g. 72000000")

    sub.add_parser("stats", help="what the database holds")

    watch = sub.add_parser("watch", help="poll SEAP and store what is new")
    watch.add_argument("--days", type=int, default=1)
    watch.add_argument("--once", action="store_true")

    fetch = sub.add_parser(
        "fetch",
        help="read Section 3 and the file list for stored notices that have neither "
        "(needs the portal)",
    )
    fetch.add_argument(
        "--limit",
        type=int,
        default=50,
        help="how many notices to read in one run; 0 or less means every one of them",
    )

    evaluate = sub.add_parser(
        "eval", help="measure the extractor against the labelled cases (no request to SEAP)"
    )
    evaluate.add_argument("--cases", default=str(DEFAULT_CASE_DIR), help="the labelled case set")

    capture = sub.add_parser(
        "capture", help="turn one notice's Section 3 into a new case to label"
    )
    capture.add_argument("c_notice_id")
    capture.add_argument("--cases", default=str(DEFAULT_CASE_DIR), help="where to write the case")
    capture.add_argument(
        "--live", action="store_true", help="fetch Section 3 from SEAP first (needs the portal)"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "stats":
        return _cmd_stats(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "explain":
        return _cmd_explain(args)
    if args.command == "requirements":
        return _cmd_requirements(args)
    if args.command == "export":
        return _cmd_export(args)
    if args.command == "watch":
        return _cmd_watch(args)
    if args.command == "fetch":
        return _cmd_fetch(args)
    if args.command == "eval":
        return _cmd_eval(args)
    if args.command == "capture":
        return _cmd_capture(args)
    return 2


def _load(args: argparse.Namespace) -> tuple[dict[str, Any], RuleSet]:
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(
            f"No profile at {profile_path}. Copy profile.example.yaml to profile.yaml "
            "and put your own numbers in.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return load_profile(profile_path), load_rules(args.rules)


def _cmd_stats(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        for table, count in store.counts().items():
            print(f"{table:>12}: {count}")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    if args.live:
        print(
            "--live needs access to e-licitatie.ro. Run it on a machine that "
            "can reach the portal.",
            file=sys.stderr,
        )
        return 2
    profile, rules = _load(args)
    with Store(args.db) as store:
        run = score_stored(store, profile, rules, cpv_prefix=args.cpv)
        for notice, verdict in run.verdicts[: args.limit]:
            print(f"{verdict.decision.value:<6} {verdict.score:>3}  {notice.notice_no:<14} "
                  f"{notice.title[:60]}")
        print()
        print(f"{run.scored} scored, {len(run.skipped_unread)} skipped (Section 3 not stored).")
        if args.cpv:
            print(
                "Note: --cpv matches the primary CPV only. Secondary codes are "
                "not stored yet, so a notice whose IT code is secondary is missed."
            )
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    profile, rules = _load(args)
    with Store(args.db) as store:
        run = score_stored(store, profile, rules)
        for notice, verdict in run.verdicts:
            if notice.c_notice_id != args.c_notice_id:
                continue
            print(f"{verdict.decision.value}  score {verdict.score}\n{notice.title}\n")
            for reason in verdict.reasons:
                mark = {"pass": "ok ", "fail": "NO ", "unknown": "?  ", "absent": "-  "}
                print(f"  {mark.get(reason.outcome or '', '   ')}{reason.text}")
                if reason.quote:
                    print(f'      "{reason.quote}"  [{reason.source_field}]')
            if verdict.unresolved:
                print(f"\n  Could not measure: {', '.join(verdict.unresolved)}")
            return 0
    print(f"No stored notice {args.c_notice_id}.", file=sys.stderr)
    return 1


def _cmd_requirements(args: argparse.Namespace) -> int:
    """Print the stored extraction for one notice, quote by quote.

    This reads the ``requirements`` table and nothing else: no profile, no
    rules, no parser run. It answers "which of the buyer's sentences produced
    that verdict", which is ground rule 1 — anything bidscout claims, Gabriel
    can check from the same row it claimed it from.
    """
    with Store(args.db) as store:
        stored = store.requirements(args.c_notice_id)
        if not stored:
            print(
                f"Nothing stored for {args.c_notice_id}. Requirements are written when a "
                "notice is scored, so run `bidscout score` first. An empty result here "
                "does not mean the buyer asks for nothing.",
                file=sys.stderr,
            )
            return 1
        when = store.requirements_extracted_at(args.c_notice_id)
        print(f"{args.c_notice_id} — read {when}\n")
        for req in stored:
            figure = f"{req.amount} {req.currency or ''}".strip() if req.amount else "no figure"
            print(f"  {req.kind:<18} {figure:<22} [{req.confidence.value}] {req.source_field}")
            print(f'      "{req.quote}"')
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Write the file the static page reads.

    The page is served by GitHub Pages, which runs no Python, so this is the
    only way data reaches it. The payload carries its own provenance, and the
    command says out loud whose figures it just wrote: committing an export
    made from a real ``profile.yaml`` publishes those numbers.
    """
    from bidscout.export import build_payload, write_export  # noqa: PLC0415 - keeps cost local

    profile, rules = _load(args)
    with Store(args.db) as store:
        payload = build_payload(
            store,
            profile,
            rules,
            cpv_prefix=args.cpv,
            source={"database": args.db, "profile": args.profile, "rules": args.rules},
        )
        path = write_export(args.out, payload)

    totals = payload["totals"]
    print(
        f"Wrote {path}: {totals['scored']} scored "
        f"({totals['go']} GO, {totals['check']} CHECK, {totals['no_go']} NO-GO), "
        f"{totals['skipped_unread']} skipped."
    )
    print(
        f"It carries the company figures from {args.profile}. Committing it publishes them."
    )
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    """Print the accuracy table. Needs no profile: it judges the reader, not the rules."""
    from bidscout.accuracy.cases import load_cases  # noqa: PLC0415 - keeps import cost local
    from bidscout.accuracy.report import format_report, measure  # noqa: PLC0415

    cases = load_cases(args.cases)
    if not cases:
        print(
            f"No cases in {args.cases}. Capture one with `bidscout capture <c-notice-id>`.",
            file=sys.stderr,
        )
        return 1
    print(format_report(measure(cases)))
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    """Write one unlabelled case. The labels are a person's job, not the tool's."""
    from bidscout.accuracy.capture import capture_case  # noqa: PLC0415 - keeps import cost local

    client = None
    if args.live:
        from bidscout.sicap.client import SicapClient  # noqa: PLC0415 - avoids importing requests

        client = SicapClient()

    with Store(args.db) as store:
        try:
            path = capture_case(store, args.c_notice_id, args.cases, client=client)
        except SectionNotStored as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"Wrote {path}. Fill in the labels, set labelled to true, then run `bidscout eval`.")
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    """Poll the portal. Kept thin, because it cannot be tested offline."""
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415 - only needed here

    from bidscout.sicap.client import SicapClient  # noqa: PLC0415 - avoids importing requests

    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)
    client = SicapClient()
    new_count = 0
    with Store(args.db) as store:
        for item in client.iter_notices(
            startPublicationDate=start.isoformat(), endPublicationDate=end.isoformat()
        ):
            if store.save_notice(notice_from_item(item)):
                new_count += 1
    print(f"{new_count} new notices stored.")
    return 0


def fetch_limit(value: int | None) -> int | None:
    """Turn the ``--limit`` flag into what the store wants.

    ``0`` on the command line means "every one of them", which the store spells
    as ``None``; passing the 0 through would ask SQLite for ``LIMIT 0`` and
    read nothing, while reporting an empty queue on a database full of unread
    notices. A negative value is treated the same as 0, because SQLite reads a
    negative LIMIT as no limit and the store now refuses one outright.
    """
    if value is None or value <= 0:
        return None
    return value


def _make_client() -> Any:
    """Build the real portal client.

    A seam, and the only reason it exists is so a test can assert that a
    command did **not** build one. ``fetch`` counts its queue before reaching
    for the network, and that claim should be checkable rather than merely
    written down.
    """
    from bidscout.sicap.client import SicapClient  # noqa: PLC0415 - avoids importing requests

    return SicapClient()


def _cmd_fetch(args: argparse.Namespace) -> int:
    """Read Section 3 and the file list for the notices ``score`` is skipping.

    ``watch`` stores notices the scorer then refuses to score, because the
    search results carry no requirements. This is the command that closes that
    circle, and it is the reason the database becomes worth reading.

    It counts the queue **before** it builds a client, so a run with nothing to
    do opens no socket. That is not only politeness: it makes the "nothing to
    fetch" path checkable with the portal unreachable.
    """
    from bidscout.fetch import fetch_missing, format_fetch_report  # noqa: PLC0415 - local cost

    limit = fetch_limit(args.limit)
    with Store(args.db) as store:
        if store.counts()["notices"] == 0:
            print(f"{args.db} holds no notices yet. Run `bidscout watch` first.")
            return 0
        waiting = store.count_missing_section3(exclude_simplified=True)
        if waiting == 0:
            simplified = store.count_missing_section3(simplified_only=True)
            print(
                "Nothing to fetch: every stored notice that can be read already has "
                "its Section 3. Run `bidscout watch` to find new ones."
            )
            if simplified:
                print(
                    f"{simplified} simplified notices are still unread, and no detail "
                    "endpoint is known for them (docs/data-sources.md, open item 1)."
                )
            return 0

        run = fetch_missing(store, _make_client(), limit=limit)

    print(format_fetch_report(run))
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
