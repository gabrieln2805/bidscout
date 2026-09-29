"""The commands a user runs most often must work with the portal unreachable."""

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
