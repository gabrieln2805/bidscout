"""A notice whose Section 3 was never stored must not be scored.

With nothing on file it would look like a notice with no requirements and
come out GO — the worst failure this tool could have.
"""

from datetime import UTC, datetime

from bidscout.models import Decision
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store

TODAY = datetime(2026, 9, 20, tzinfo=UTC)


def test_an_unread_notice_is_skipped_and_counted(
    tmp_path, notice_item, strong_profile, rules
) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        run = score_stored(store, strong_profile, rules, today=TODAY)
        assert run.scored == 0
        assert [n.notice_no for n in run.skipped_unread] == ["CN1096282"]


def test_a_read_notice_is_scored(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        run = score_stored(store, strong_profile, rules, today=TODAY)
        assert run.scored == 1
        assert run.verdicts[0][1].decision is Decision.GO


def test_section3_is_re_read_every_run_so_a_parser_fix_applies(
    tmp_path, notice_item, section3_full, small_profile, rules
) -> None:
    """The saved verdict is never trusted; only the stored raw section is."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        assert score_stored(store, small_profile, rules, today=TODAY).verdicts[0][1].decision is (
            Decision.NO_GO
        )
        # The buyer publishes a corrected, lower threshold.
        corrected = dict(section3_full.raw)
        corrected["efCriteriaMin"] = "<p>cel putin <b>900.000,00 Lei</b></p>"
        store.save_section3("1096282", corrected)
        assert score_stored(store, small_profile, rules, today=TODAY).verdicts[0][1].decision is (
            Decision.GO
        )


def test_results_come_back_with_the_strongest_first(
    tmp_path, notice_item, section3_full, section3_vague, strong_profile, rules
) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        second = {**notice_item, "cNoticeId": 1096999, "noticeNo": "CN1096999"}
        store.save_notice(notice_from_item(second))
        store.save_section3("1096999", section3_vague.raw)
        run = score_stored(store, strong_profile, rules, today=TODAY)
        scores = [verdict.score for _, verdict in run.verdicts]
        assert scores == sorted(scores, reverse=True)


def test_cpv_filter_matches_the_primary_code_only(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    """A documented limit: secondary CPV codes are not stored yet."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        assert score_stored(store, strong_profile, rules, cpv_prefix="72", today=TODAY).scored == 1
        assert score_stored(store, strong_profile, rules, cpv_prefix="45", today=TODAY).scored == 0
