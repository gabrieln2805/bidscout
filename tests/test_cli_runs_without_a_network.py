"""The commands a user runs most often must work with the portal unreachable."""

from pathlib import Path

import pytest
import yaml

from bidscout.cli import main
from bidscout.pipeline import notice_from_item
from bidscout.store.db import Store


@pytest.fixture
def ready_db(tmp_path, notice_item, section3_full, strong_profile):
    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump(strong_profile), encoding="utf-8")
    return db, profile


def test_stats_reports_what_is_stored(ready_db, capsys) -> None:
    db, _ = ready_db
    assert main(["--db", str(db), "stats"]) == 0
    assert "notices: 1" in capsys.readouterr().out


def test_score_ranks_from_the_database(ready_db, capsys) -> None:
    db, profile = ready_db
    assert main(["--db", str(db), "--profile", str(profile), "score"]) == 0
    out = capsys.readouterr().out
    assert "GO" in out
    assert "1 scored" in out


def test_score_prints_the_cpv_limit_rather_than_hide_it(ready_db, capsys) -> None:
    db, profile = ready_db
    main(["--db", str(db), "--profile", str(profile), "score", "--cpv", "72"])
    assert "primary CPV only" in capsys.readouterr().out


def test_explain_shows_the_buyers_own_sentence(ready_db, capsys) -> None:
    db, profile = ready_db
    assert main(["--db", str(db), "--profile", str(profile), "explain", "1096282"]) == 0
    assert "2.700.000,00" in capsys.readouterr().out


def test_live_scoring_refuses_instead_of_hanging(ready_db, capsys) -> None:
    """The cloud sandbox cannot reach the portal; say so and stop."""
    db, profile = ready_db
    assert main(["--db", str(db), "--profile", str(profile), "score", "--live"]) == 2
    assert "e-licitatie.ro" in capsys.readouterr().err


def test_a_missing_profile_is_an_instruction_not_a_traceback(tmp_path, capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--db", str(tmp_path / "x.sqlite3"), "--profile", "nope.yaml", "score"])
    assert "profile.example.yaml" in capsys.readouterr().err


CASE_DIR = Path(__file__).parents[1] / "eval" / "cases"


def test_eval_prints_the_accuracy_table(capsys) -> None:
    assert main(["eval", "--cases", str(CASE_DIR)]) == 0
    out = capsys.readouterr().out
    assert "cover" in out
    assert "labelled cases measured" in out


def test_eval_needs_no_profile(capsys) -> None:
    """It measures the reader, not the rules, so a missing profile must not stop it."""
    assert main(["--profile", "nowhere.yaml", "eval", "--cases", str(CASE_DIR)]) == 0
    assert "cover" in capsys.readouterr().out


def test_eval_with_no_cases_says_how_to_make_one(tmp_path, capsys) -> None:
    assert main(["eval", "--cases", str(tmp_path / "empty")]) == 1
    assert "bidscout capture" in capsys.readouterr().err


def test_capture_writes_a_case_from_the_database(ready_db, tmp_path, capsys) -> None:
    db, _ = ready_db
    cases = tmp_path / "cases"
    assert main(["--db", str(db), "capture", "1096282", "--cases", str(cases)]) == 0
    assert (cases / "cn1096282.json").exists()
    assert "Fill in the labels" in capsys.readouterr().out


def test_capture_without_a_stored_section_is_an_instruction_not_a_traceback(
    tmp_path, notice_item, capsys
) -> None:
    db = tmp_path / "empty.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
    assert main(["--db", str(db), "capture", "1096282", "--cases", str(tmp_path / "c")]) == 1
    assert "no Section 3 stored" in capsys.readouterr().err


def test_fetch_with_nothing_missing_builds_no_client(ready_db, capsys, monkeypatch) -> None:
    """The queue is counted before a client is built, and that is asserted.

    ``fetch`` needs the portal by definition, so this is the one path through
    it that can be checked here. It matters twice over: a user running
    ``fetch`` twice should not reach for the network to learn it has nothing to
    do, and on Gabriel's machine — where the portal *is* reachable — a
    regression here would make the test suite itself call e-licitatie.ro.
    """
    import bidscout.cli as cli

    def _refuse() -> object:
        raise AssertionError("fetch built a portal client with nothing to fetch")

    monkeypatch.setattr(cli, "_make_client", _refuse)
    db, _ = ready_db
    assert main(["--db", str(db), "fetch"]) == 0
    assert "Nothing to fetch" in capsys.readouterr().out


def test_fetch_prints_the_report_for_what_it_read(tmp_path, notice_item, capsys, monkeypatch):
    """The fetching branch itself, reached through the same seam with a fake.

    Without this, every line of ``_cmd_fetch`` after the queue count would be
    unreachable from the suite — including the ``--limit`` translation below.
    """
    import bidscout.cli as cli
    from bidscout.pipeline import notice_from_item as from_item

    class _Fake:
        def __init__(self) -> None:
            self.asked: list[str] = []

        def get_section3(self, init_notice_id):
            self.asked.append(str(init_notice_id))
            return {"efCriteriaMin": "<p>cel putin <b>900.000,00 Lei</b></p>"}

        def get_documents(self, init_notice_id):
            return {}

    fake = _Fake()
    monkeypatch.setattr(cli, "_make_client", lambda: fake)
    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(from_item(notice_item))
    assert main(["--db", str(db), "fetch"]) == 0
    assert fake.asked == ["384463"]
    assert "Section 3 is now on file for 1 of 1 notice" in capsys.readouterr().out


def test_fetch_limit_zero_asks_for_everything_not_for_nothing(tmp_path, notice_item) -> None:
    """``LIMIT 0`` would read nothing and report an empty queue on a full one.

    The flag says 0 means every notice, so it has to become ``None`` before it
    reaches SQLite. Asserting that argparse returned a 0 would prove nothing;
    this asserts the translation and what the store then does with it.
    """
    from bidscout.cli import fetch_limit

    assert fetch_limit(0) is None
    assert fetch_limit(-5) is None
    assert fetch_limit(50) == 50
    assert fetch_limit(None) is None

    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        for index in range(3):
            store.save_notice(
                notice_from_item({**notice_item, "cNoticeId": index, "noticeNo": f"CN{index}"})
            )
        assert len(list(store.notices_missing_section3(limit=fetch_limit(0)))) == 3
        assert len(list(store.notices_missing_section3(limit=fetch_limit(2)))) == 2


def test_fetch_defaults_to_a_bounded_run() -> None:
    """A first pass over a large database should be polite without being asked."""
    from bidscout.cli import build_parser

    assert build_parser().parse_args(["fetch"]).limit == 50
