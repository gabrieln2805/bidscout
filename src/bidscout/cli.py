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
from bidscout.decide.rules import RuleSet, load_profile, load_rules
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import DEFAULT_DB_PATH, Store

OFFLINE_COMMANDS = frozenset({"score", "stats", "explain"})


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

    sub.add_parser("stats", help="what the database holds")

    watch = sub.add_parser("watch", help="poll SEAP and store what is new")
    watch.add_argument("--days", type=int, default=1)
    watch.add_argument("--once", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "stats":
        return _cmd_stats(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "explain":
        return _cmd_explain(args)
    if args.command == "watch":
        return _cmd_watch(args)
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
            print(f"{table:>10}: {count}")
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
                print(f"  - {reason.text}")
                if reason.quote:
                    print(f'      "{reason.quote}"  [{reason.source_field}]')
            if verdict.unresolved:
                print(f"\n  Could not measure: {', '.join(verdict.unresolved)}")
            return 0
    print(f"No stored notice {args.c_notice_id}.", file=sys.stderr)
    return 1


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


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
