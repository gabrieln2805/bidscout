"""Glue: portal item -> Notice, and stored notice -> Verdict.

Kept apart from both the client and the store so that a change to the
portal's field names touches one function, and so that scoring can run with
no network at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from bidscout.decide.engine import decide
from bidscout.decide.rules import RuleSet
from bidscout.extract.gates import extract_requirements
from bidscout.models import Notice, Verdict
from bidscout.store.db import Store


def notice_from_item(item: dict[str, Any]) -> Notice:
    """Build a ``Notice`` from one row of ``GetCNoticeList``.

    The whole item is kept in ``raw``. Every named field below is a
    convenience copy for querying, never the only copy.
    """
    return Notice(
        c_notice_id=str(item.get("cNoticeId") or item.get("noticeId") or ""),
        notice_no=str(item.get("noticeNo") or ""),
        init_notice_id=_as_str(item.get("noticeId")),
        title=str(item.get("contractTitle") or ""),
        buyer=str(item.get("contractingAuthorityNameAndFN") or ""),
        cpv=_cpv_code(item.get("cpvCodeAndName")),
        estimated_value_ron=_as_decimal(item.get("estimatedValueRon")),
        published_at=_as_str(item.get("noticeStateDate")),
        deadline_at=_as_str(item.get("minTenderReceiptDeadline")),
        notice_type_id=_as_int(item.get("sysNoticeTypeId")),
        raw=item,
    )


@dataclass
class ScoreRun:
    """What one pass of the scorer produced, including what it refused to score."""

    verdicts: list[tuple[Notice, Verdict]]
    skipped_unread: list[Notice]

    @property
    def scored(self) -> int:
        return len(self.verdicts)


def score_stored(
    store: Store,
    profile: dict[str, Any],
    rules: RuleSet,
    cpv_prefix: str | None = None,
    today: datetime | None = None,
) -> ScoreRun:
    """Score every stored notice that has been read in full.

    Section 3 is re-read from the database on every run rather than trusting a
    saved list of requirements. A fix to the extractor therefore applies on the
    next score, with no new request to the portal.

    A notice with no stored Section 3 is **skipped and counted**, never scored.
    With nothing on file it would look like a notice with no requirements and
    come out GO, which is the worst possible failure for this tool.
    """
    verdicts: list[tuple[Notice, Verdict]] = []
    skipped: list[Notice] = []

    for notice in store.notices(cpv_prefix=cpv_prefix):
        section3 = store.section3(notice.c_notice_id)
        if section3 is None:
            skipped.append(notice)
            continue
        requirements = extract_requirements(section3)
        context = {
            "cpv": notice.cpv,
            "estimated_value_ron": notice.estimated_value_ron,
            "days_to_deadline": _days_to(notice.deadline_at, today),
        }
        verdict = decide(requirements, profile, rules, context)
        store.save_verdict(notice.c_notice_id, str(profile.get("company_name", "default")), verdict)
        verdicts.append((notice, verdict))

    verdicts.sort(key=lambda pair: pair[1].score, reverse=True)
    return ScoreRun(verdicts=verdicts, skipped_unread=skipped)


def _days_to(deadline: str | None, today: datetime | None) -> int | None:
    """Days from now to the deadline, or None when the date is unreadable."""
    if not deadline:
        return None
    try:
        when = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = today or datetime.now(when.tzinfo)
    return (when - now).days


def _cpv_code(value: Any) -> str | None:
    """Take "72000000-5 - Servicii IT..." down to "72000000"."""
    if not value:
        return None
    head = str(value).strip().split(" ", 1)[0]
    return head.split("-", 1)[0] or None


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _as_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
