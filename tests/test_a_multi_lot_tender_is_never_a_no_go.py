"""A tender split into lots must not be scored as if it were one thing.

The notice-level turnover or experience figure may be the total for every lot
together, while the company would bid for one lot. Comparing a company against
that total and printing NO-GO is exactly the "we could not tell" that ground
rule 2 forbids, so an unread lot structure holds the verdict at CHECK.
"""

from datetime import UTC, datetime

from bidscout.decide.engine import decide
from bidscout.extract.gates import extract_requirements
from bidscout.models import Decision
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store

TODAY = datetime(2026, 9, 20, tzinfo=UTC)


def test_a_shortfall_on_a_multi_lot_tender_is_check_not_no_go(
    section3_full, small_profile, rules
) -> None:
    """The trap: the very same notice without lots is a legitimate NO-GO.

    Both assertions matter. Dropping the first would let a change that turned
    every verdict into CHECK pass as if it had fixed something.
    """
    requirements = extract_requirements(section3_full)
    whole = decide(requirements, small_profile, rules, {"has_lots": False})
    assert whole.decision is Decision.NO_GO

    split = decide(requirements, small_profile, rules, {"has_lots": True})
    assert split.decision is Decision.CHECK
    assert any("lots" in item for item in split.unresolved)


def test_a_multi_lot_tender_is_not_a_go_either(section3_full, strong_profile, rules) -> None:
    """A company that clears the notice-level figures still has not been measured."""
    verdict = decide(extract_requirements(section3_full), strong_profile, rules, {"has_lots": True})
    assert verdict.decision is Decision.CHECK
    assert any("split into lots" in reason.text for reason in verdict.reasons)


def test_has_lots_survives_a_round_trip_through_the_database(tmp_path, notice_item) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item({**notice_item, "hasLots": True}))
        assert next(store.notices()).has_lots is True


def test_a_notice_that_gains_lots_on_a_repoll_is_not_left_as_it_was(
    tmp_path, notice_item
) -> None:
    """A corrigendum that splits a tender must not leave yesterday's GO standing.

    Unlike the other convenience columns, ``has_lots`` is refreshed when a
    notice is seen again, because it changes the verdict rather than only the
    display.
    """
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        assert next(store.notices()).has_lots is False
        store.save_notice(notice_from_item({**notice_item, "hasLots": True}))
        assert next(store.notices()).has_lots is True


def test_the_flag_travels_from_the_portal_item_to_the_verdict(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    """End to end, offline: ``hasLots`` in the item, CHECK out of the scorer."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item({**notice_item, "hasLots": True}))
        store.save_section3("1096282", section3_full.raw)
        run = score_stored(store, strong_profile, rules, today=TODAY)
        assert run.verdicts[0][1].decision is Decision.CHECK
