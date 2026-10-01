"""A verdict must be traceable to the buyer's sentences without re-parsing.

Ground rule 1: anything bidscout checks, Gabriel must be able to check. The
``requirements`` table is that trace — every figure the extractor read, with
the quote and the Section 3 field it came from beside it. It is derived data:
``sections.section3_raw`` stays the only source of truth, and the scorer still
re-reads it on every run.
"""

from decimal import Decimal

import pytest

from bidscout.cli import main
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store


@pytest.fixture
def scored_db(tmp_path, notice_item, section3_full, strong_profile, rules):
    """One notice, read and scored, so the trace is on disk."""
    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        score_stored(store, strong_profile, rules)
    return db


def test_scoring_writes_down_what_it_read(scored_db) -> None:
    with Store(scored_db) as store:
        kinds = {req.kind for req in store.requirements("1096282")}
        assert {"turnover", "experience"} <= kinds


def test_a_stored_amount_comes_back_as_the_number_the_buyer_wrote(scored_db) -> None:
    """The trap: stored as a REAL, 2.700.000,00 Lei returns as a float.

    The column is TEXT and the value is rebuilt as ``Decimal`` for that reason.
    A float here would quietly move a hard gate by a fraction of a leu.
    """
    with Store(scored_db) as store:
        turnover = {req.kind: req for req in store.requirements("1096282")}["turnover"]
        assert isinstance(turnover.amount, Decimal)
        assert turnover.amount == Decimal("2700000.00")


def test_every_stored_requirement_still_carries_its_quote(scored_db) -> None:
    with Store(scored_db) as store:
        stored = store.requirements("1096282")
        assert stored
        assert all(req.quote.strip() for req in stored)
        assert all(req.source_field for req in stored)
        assert any("2.700.000,00" in req.quote for req in stored)


def test_scoring_twice_replaces_the_trace_instead_of_piling_it_up(
    scored_db, strong_profile, rules
) -> None:
    with Store(scored_db) as store:
        before = store.counts()["requirements"]
        score_stored(store, strong_profile, rules)
        assert store.counts()["requirements"] == before


def test_the_trace_follows_a_corrected_section_3(scored_db, strong_profile, rules) -> None:
    """The raw section stays the source of truth, so the trace moves with it."""
    with Store(scored_db) as store:
        store.save_section3("1096282", {"efCriteriaMin": "<p>cel putin <b>900.000,00 Lei</b></p>"})
        score_stored(store, strong_profile, rules)
        turnover = {req.kind: req for req in store.requirements("1096282")}["turnover"]
        assert turnover.amount == Decimal("900000.00")


def test_a_notice_nobody_scored_has_no_trace_at_all(tmp_path, notice_item) -> None:
    """Empty means "not read yet", which is not the same as "asks for nothing"."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        assert store.requirements("1096282") == []
        assert store.requirements_extracted_at("1096282") is None


def test_the_requirements_command_prints_the_quote_and_the_field(scored_db, capsys) -> None:
    assert main(["--db", str(scored_db), "requirements", "1096282"]) == 0
    out = capsys.readouterr().out
    assert "2.700.000,00" in out
    assert "efCriteriaMin" in out


def test_the_requirements_command_needs_no_profile(scored_db, capsys) -> None:
    """It reports what was read, not what it means for a company."""
    argv = ["--db", str(scored_db), "--profile", "nowhere.yaml", "requirements", "1096282"]
    assert main(argv) == 0
    assert "turnover" in capsys.readouterr().out


def test_an_empty_trace_never_reads_as_the_buyer_asking_for_nothing(
    tmp_path, notice_item, capsys
) -> None:
    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
    assert main(["--db", str(db), "requirements", "1096282"]) == 1
    err = capsys.readouterr().err
    assert "bidscout score" in err
    assert "does not mean the buyer asks for nothing" in err
