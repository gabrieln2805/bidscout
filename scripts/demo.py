"""Build a small database from the captured fixtures and score it.

This exists so that a new reader can see the whole pipeline work in one
command, on a machine with no access to e-licitatie.ro. It writes to
``data/demo.sqlite3`` and never touches a real collection.
"""

from __future__ import annotations

import json
from pathlib import Path

from bidscout.decide.rules import load_profile, load_rules
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CASES = ROOT / "eval" / "cases"
DEMO_DB = ROOT / "data" / "demo.sqlite3"


def main() -> int:
    DEMO_DB.unlink(missing_ok=True)
    item = json.loads((FIXTURES / "notice_item.json").read_text(encoding="utf-8"))
    full = json.loads((FIXTURES / "section3_cn1096282.json").read_text(encoding="utf-8"))
    vague = json.loads((FIXTURES / "section3_vague.json").read_text(encoding="utf-8"))
    # The third labelled case, reused so the demo shows a notice whose guarantee
    # the buyer stated in euro and whose turnover rule names only the three
    # financial years. Both are traps the extractor has to refuse to guess at.
    euro = json.loads((CASES / "cn1097222.json").read_text(encoding="utf-8"))["section3_raw"]

    with Store(DEMO_DB) as store:
        store.save_notice(notice_from_item(item))
        store.save_section3("1096282", full)
        store.save_notice(
            notice_from_item(
                {**item, "cNoticeId": 1096999, "noticeNo": "CN1096999",
                 "contractTitle": "Servicii de mentenanta aplicatii"}
            )
        )
        store.save_section3("1096999", vague)
        store.save_notice(
            notice_from_item(
                {**item, "cNoticeId": 1097222, "noticeNo": "CN1097222",
                 "contractTitle": "Servicii de dezvoltare portal web si integrare",
                 "estimatedValueRon": 620000.0}
            )
        )
        store.save_section3("1097222", euro)
        # A fourth notice we have not read in full, to show it is skipped.
        store.save_notice(
            notice_from_item(
                {**item, "cNoticeId": 1097111, "noticeNo": "CN1097111",
                 "contractTitle": "Licente software"}
            )
        )

        profile = load_profile(ROOT / "config" / "profile.example.yaml")
        rules = load_rules(ROOT / "config" / "rules" / "it.yaml")
        run = score_stored(store, profile, rules)

        print(f"Company: {profile['company_name']}   Rules: {rules.name}\n")
        for notice, verdict in run.verdicts:
            print(f"{verdict.decision.value:<6} {verdict.score:>3}  {notice.notice_no:<12} "
                  f"{notice.title[:52]}")
            for reason in verdict.reasons:
                print(f"         - {reason.text}")
            print()
        print(f"{run.scored} scored, {len(run.skipped_unread)} skipped "
              f"(Section 3 not stored): "
              f"{', '.join(n.notice_no for n in run.skipped_unread)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
