"""``fetch`` is the step between ``watch`` and ``score``.

``watch`` stores what the search results carry, and they carry no
requirements, so the scorer skips every notice ``watch`` ever stored. These
tests cover the queue ``fetch`` works through, what it stores, what it refuses
to ask for, and what it does when the portal says no.

The related guard — that a section the reader cannot understand is CHECK and
never GO — lives in ``test_an_unread_section_is_never_a_go.py``, because it is
enforced in ``decide`` rather than here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from bidscout.errors import NoticeNotFound
from bidscout.fetch import fetch_missing, format_fetch_report
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.sicap.client import SicapClient
from bidscout.store.db import Store

TODAY = datetime(2026, 9, 20, tzinfo=UTC)

#: What the portal sends for a notice whose section does not exist: the
#: identifiers echoed back, and not one word of the buyer's own.
NO_SECTION: dict[str, Any] = {"initNoticeId": 384463, "sysNoticeTypeId": 2}


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.content = b""

    def json(self) -> Any:
        return self._payload


class _Portal:
    """A fake portal, routed by endpoint and by ``initNoticeId``.

    Driven through a real ``SicapClient`` on purpose, so these tests exercise
    the URL and parameter building the client does, and a fake answering a URL
    nobody calls would be caught by the assertion at the bottom.
    """

    def __init__(
        self,
        sections: dict[str, Any] | None = None,
        documents: dict[str, Any] | None = None,
        raises: dict[str, Exception] | None = None,
    ) -> None:
        self.sections = sections or {}
        self.documents = documents or {}
        self.raises = raises or {}
        self.section_calls: list[str] = []
        self.document_calls: list[str] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        key = str((params or {}).get("initNoticeId"))
        if "GetSection3View" in url:
            self.section_calls.append(key)
            if key in self.raises:
                raise self.raises[key]
            return _Response(self.sections.get(key, NO_SECTION))
        if "GetDfNoticeSectionFiles" in url:
            self.document_calls.append(key)
            return _Response(self.documents.get(key, {}))
        raise AssertionError(f"fetch called an endpoint it has no business calling: {url}")

    def post(self, url: str, json: dict[str, Any] | None = None) -> Any:
        raise AssertionError("fetch must never run a search; watch does that")


def _client(portal: _Portal) -> SicapClient:
    return SicapClient(transport=portal, pause_seconds=0.0)


def _notice(notice_item: dict[str, Any], **changes: Any) -> Any:
    return notice_from_item({**notice_item, **changes})


@pytest.fixture
def one_unread(tmp_path, notice_item):
    """A database holding exactly the notice ``watch`` would have stored."""
    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
    return db


# ------------------------------------------------------------- the happy path


def test_what_watch_left_unscorable_fetch_makes_scorable(
    one_unread, section3_full, strong_profile, rules
) -> None:
    """End to end, and the whole reason this command exists."""
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        before = score_stored(store, strong_profile, rules, today=TODAY)
        assert (before.scored, len(before.skipped_unread)) == (0, 1)

        run = fetch_missing(store, _client(portal))
        assert run.fetched == ["CN1096282"]

        after = score_stored(store, strong_profile, rules, today=TODAY)
        assert (after.scored, after.skipped_unread) == (1, [])


def test_the_section_is_asked_for_by_c_notice_id(one_unread, section3_full) -> None:
    """The parameter is called ``initNoticeId`` and takes the ``cNoticeId``.

    Confirmed live on 2 October 2026. Sending the ``noticeId`` (384463 here)
    was the first bug the live portal found: it answers "not found" with 200.
    """
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        fetch_missing(store, _client(portal))
        assert portal.section_calls == ["1096282"]
        assert store.section3("1096282") is not None


def test_the_payload_is_stored_exactly_as_it_arrived(one_unread, section3_full) -> None:
    """Ground rule 3: a parser rewrite is replayed from this row."""
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        fetch_missing(store, _client(portal))
        assert store.section3("1096282").raw == section3_full.raw


def test_a_section_the_reader_cannot_parse_is_still_stored(one_unread) -> None:
    """Keeping it is what lets a later parser fix be replayed from disk.

    Throwing it away would also leave the notice in the queue to be re-fetched
    on every future run, which is an unbounded repeat against somebody else's
    server. The verdict is held at CHECK instead — see
    ``test_an_unread_section_is_never_a_go.py``.
    """
    with Store(one_unread) as store:
        run = fetch_missing(store, _client(_Portal()))  # answers NO_SECTION
        assert store.section3("1096282").raw == NO_SECTION
    assert run.fetched == ["CN1096282"]


def test_a_notice_already_read_is_never_asked_for_again(one_unread, section3_full) -> None:
    """A second run with nothing new to do must make no request at all."""
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        fetch_missing(store, _client(portal))
        portal.section_calls.clear()
        second = fetch_missing(store, _client(portal))
    assert portal.section_calls == []
    assert second.considered == 0


def test_an_unparsed_section_is_not_re_requested_either(one_unread) -> None:
    """The queue has to drain even for notices the portal answered thinly.

    An earlier version of this module refused to store such a payload, which
    left the notice in the queue for ever and asked the portal for it again on
    every single run.
    """
    portal = _Portal()
    with Store(one_unread) as store:
        fetch_missing(store, _client(portal))
        fetch_missing(store, _client(portal))
        fetch_missing(store, _client(portal))
    assert portal.section_calls == ["1096282"]


# ------------------------------------------------------- what it refuses to ask


def test_a_simplified_notice_is_left_out_of_the_queue(tmp_path, notice_item) -> None:
    """SCN notices have no detail endpoint, so asking is a request we can skip."""
    portal = _Portal()
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(_notice(notice_item, cNoticeId=9, noticeNo="SCN9", sysNoticeTypeId=17))
        run = fetch_missing(store, _client(portal))
    assert portal.section_calls == []
    assert run.simplified_waiting == 1
    assert "no detail endpoint is known" in format_fetch_report(run)


def test_simplified_notices_cannot_starve_the_ones_that_can_be_read(
    tmp_path, notice_item, section3_full
) -> None:
    """The reason the filter is in SQL and not in the loop.

    Simplified notices are 60% of what the portal publishes and can never be
    fetched, so they never leave the queue. Counted against ``--limit`` they
    would sit at the front of every run for ever and the readable notices
    behind them would never be reached at all.
    """
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(tmp_path / "t.sqlite3") as store:
        for index in range(3):
            store.save_notice(
                _notice(
                    notice_item,
                    cNoticeId=9000 + index,
                    noticeNo=f"SCN900{index}",
                    sysNoticeTypeId=17,
                    noticeStateDate=f"2026-09-2{index + 1}T00:00:00Z",
                )
            )
        store.save_notice(notice_from_item(notice_item))  # older, and readable
        run = fetch_missing(store, _client(portal), limit=3)
    assert run.fetched == ["CN1096282"]
    assert run.simplified_waiting == 3


def test_a_notice_numbered_scn_is_recognised_without_the_type_id(tmp_path, notice_item) -> None:
    """The portal has been seen to send one and not the other."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(_notice(notice_item, cNoticeId=9, noticeNo="SCN9", sysNoticeTypeId=None))
        assert store.count_missing_section3(simplified_only=True) == 1
        assert store.count_missing_section3(exclude_simplified=True) == 0


# ---------------------------------------------------------------- partial runs


def test_one_notice_the_portal_refuses_does_not_end_the_run(
    tmp_path, notice_item, section3_full
) -> None:
    """Forty-nine good notices are not thrown away because the fiftieth is bad."""
    portal = _Portal(
        sections={"1096282": section3_full.raw},
        raises={"1096999": NoticeNotFound("no Section 3 for cNoticeId=1096999")},
    )
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_notice(
            _notice(
                notice_item,
                cNoticeId=1096999,
                noticeId=999,
                noticeNo="CN1096999",
                noticeStateDate="2026-09-19T09:14:00Z",
            )
        )
        run = fetch_missing(store, _client(portal))
        assert store.section3("1096282") is not None
        assert store.section3("1096999") is None
    assert run.fetched == ["CN1096282"]
    assert [label for label, _ in run.failed] == ["CN1096999"]
    assert "no Section 3 for cNoticeId=1096999" in format_fetch_report(run)


def test_an_unexpected_failure_keeps_what_was_already_stored(
    tmp_path, notice_item, section3_full
) -> None:
    """A failure that is not the portal saying no stops the run, on purpose.

    Repeating an unknown fault once per notice would be fifty pointless
    requests to somebody else's server. Everything fetched before it is
    already committed, so stopping costs nothing.
    """
    # The queue is newest first, so the good notice is dated *after* the bad one
    # to put it genuinely before the abort. Without that the test would pass for
    # the wrong reason: nothing stored, because nothing was reached.
    portal = _Portal(
        sections={"1096282": section3_full.raw},
        raises={"1096999": RuntimeError("the transport broke")},
    )
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_notice(
            _notice(
                notice_item,
                cNoticeId=1096999,
                noticeId=999,
                noticeNo="CN1096999",
                noticeStateDate="2026-09-17T09:14:00Z",
            )
        )
        with pytest.raises(RuntimeError):
            fetch_missing(store, _client(portal))
        assert store.section3("1096282") is not None
        assert store.section3("1096999") is None


# ------------------------------------------------------------------- the queue


def test_the_queue_is_what_the_scorer_skips(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    """Two views of one fact. Unfiltered, they must agree."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        store.save_notice(_notice(notice_item, cNoticeId=1097111, noticeNo="CN1097111"))
        skipped = score_stored(store, strong_profile, rules, today=TODAY).skipped_unread
        queued = list(store.notices_missing_section3())
    assert [n.notice_no for n in skipped] == [n.notice_no for n in queued] == ["CN1097111"]


def test_the_queue_is_newest_first(tmp_path, notice_item) -> None:
    """A tender published today has a deadline worth catching."""
    with Store(tmp_path / "t.sqlite3") as store:
        for index in range(3):
            store.save_notice(
                _notice(
                    notice_item,
                    cNoticeId=3000 + index,
                    noticeNo=f"CN300{index}",
                    noticeStateDate=f"2026-09-0{index + 1}T00:00:00Z",
                )
            )
        assert [n.notice_no for n in store.notices_missing_section3()] == [
            "CN3002",
            "CN3001",
            "CN3000",
        ]


def test_a_limit_bounds_one_run(tmp_path, notice_item, section3_full) -> None:
    """A first pass over a large database is a series of polite visits."""
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(tmp_path / "t.sqlite3") as store:
        for index in range(4):
            store.save_notice(
                _notice(notice_item, cNoticeId=2000 + index, noticeNo=f"CN200{index}")
            )
        run = fetch_missing(store, _client(portal), limit=2)
    assert run.considered == 2


def test_no_limit_means_the_whole_queue(tmp_path, notice_item) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        for index in range(4):
            store.save_notice(
                _notice(notice_item, cNoticeId=2000 + index, noticeNo=f"CN200{index}")
            )
        assert len(list(store.notices_missing_section3(limit=None))) == 4


def test_a_negative_limit_is_refused_rather_than_read_as_unlimited(
    tmp_path, notice_item
) -> None:
    """SQLite reads a negative LIMIT as no limit at all.

    An off-by-one in a caller would therefore turn a bounded, polite run into
    a run over the whole database, which is the opposite of what the flag is
    for. The store refuses it instead of guessing.
    """
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        with pytest.raises(ValueError, match="negative"):
            list(store.notices_missing_section3(limit=-1))


def test_counting_the_queue_agrees_with_walking_it(tmp_path, notice_item) -> None:
    """The CLI counts and ``fetch`` walks; they must not be able to disagree."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_notice(_notice(notice_item, cNoticeId=9, noticeNo="SCN9", sysNoticeTypeId=17))
        assert store.count_missing_section3() == 2
        assert store.count_missing_section3(exclude_simplified=True) == 1
        assert len(list(store.notices_missing_section3(exclude_simplified=True))) == 1


# ------------------------------------------------------------------ the report


def test_the_report_reads_properly_when_there_is_only_one(one_unread, section3_full) -> None:
    """The report is the only face ``fetch`` has; it should not read like a draft."""
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        report = format_fetch_report(fetch_missing(store, _client(portal)))
    assert "1 of 1 notice," in report
    assert "notices," not in report


def test_the_report_tells_the_reader_what_to_run_next(one_unread, section3_full) -> None:
    portal = _Portal(sections={"1096282": section3_full.raw})
    with Store(one_unread) as store:
        report = format_fetch_report(fetch_missing(store, _client(portal)))
    assert "bidscout score" in report
