"""The web page can only be as honest as the file it reads.

GitHub Pages runs no Python, so ``bidscout export`` is the only route from the
database to the page. Everything the page claims has to be in this file, and
nothing in this file may be less exact than the database it came from.

The export reads the ``app`` marts dbt builds, never the landing tables, so
these tests run the real ``dbt build``. It takes seconds, so the payload is
built once per module and the read-only tests share it.

The money rule is the sharp one. ``json`` has no decimal type: an amount written
as a JSON number comes back as a float, and a float is no longer the figure the
buyer wrote. Every amount is therefore a string, and the exporter refuses a
float outright rather than publishing a rounded hard gate.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from bidscout.cli import main
from bidscout.export import SCHEMA_VERSION, build_payload
from bidscout.pipeline import notice_from_item
from bidscout.store.db import Store

ROOT = Path(__file__).parents[1]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))

#: The same company as the ``strong_profile`` fixture, which is function-scoped.
STRONG = {
    "company_name": "Strong SRL",
    "average_turnover_ron": 6000000,
    "similar_experience_ron": 4000000,
    "available_guarantee_ron": 100000,
    "min_contract_ron": 50000,
    "max_contract_ron": 3000000,
    "cpv_watchlist": ["72000000"],
}


def _three_notices(path: Path) -> Store:
    """Two notices read in full and one never read, so skipping is exercised."""
    item = load_fixture("notice_item.json")
    store = Store(path)
    store.save_notice(notice_from_item(item))
    store.save_section3("1096282", load_fixture("section3_cn1096282.json"))
    store.save_notice(notice_from_item({**item, "cNoticeId": 1096999, "noticeNo": "CN1096999"}))
    store.save_section3("1096999", load_fixture("section3_vague.json"))
    store.save_notice(notice_from_item({**item, "cNoticeId": 1097111, "noticeNo": "CN1097111"}))
    return store


@pytest.fixture
def scored_store(tmp_path):
    store = _three_notices(tmp_path / "t.sqlite3")
    yield store
    store.close()


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    """One real export — score, ``dbt build``, read the app marts — shared below."""
    from bidscout.decide.rules import load_rules

    rules = load_rules(ROOT / "config" / "rules" / "it.yaml")
    with _three_notices(tmp_path_factory.mktemp("export") / "t.sqlite3") as store:
        return build_payload(
            store, STRONG, rules, source={"database": "data/demo.sqlite3"}
        )


def _walk(value):
    """Yield every scalar in a parsed JSON tree."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


def test_no_amount_is_ever_a_json_number(payload) -> None:
    """The trap: JSON has no decimals, so a number here is a float on the way back.

    This walks the whole round-tripped payload rather than checking the fields we
    happened to think of, so a float added to the export later fails here.
    """
    reloaded = json.loads(json.dumps(payload))
    floats = [value for value in _walk(reloaded) if isinstance(value, float)]
    assert floats == []


def test_the_exporter_refuses_a_float_rather_than_rounding_it(
    scored_store, rules
) -> None:
    """A profile figure that arrived as a float has already lost its exactness."""
    careless = {"company_name": "Float SRL", "average_turnover_ron": 2700000.00}
    with pytest.raises(TypeError, match="float"):
        build_payload(scored_store, careless, rules)


def test_an_amount_survives_as_the_string_the_buyer_wrote(payload) -> None:
    tender = {t["notice_no"]: t for t in payload["tenders"]}["CN1096282"]
    turnover = {r["kind"]: r for r in tender["requirements"]}["turnover"]
    assert turnover["amount"] == "2700000.00"
    assert Decimal(turnover["amount"]) == Decimal("2700000.00")


def test_every_reason_carries_its_quote_its_field_and_its_outcome(payload) -> None:
    """The page marks each gate from ``outcome``; it must never parse the text."""
    reasons = [reason for tender in payload["tenders"] for reason in tender["reasons"]]
    assert reasons
    assert all(reason["outcome"] in {"pass", "fail", "unknown", "absent"} for reason in reasons)
    quoted = [reason for reason in reasons if reason["quote"]]
    assert quoted
    assert all(reason["source_field"] for reason in quoted)


def test_the_notices_nobody_read_are_exported_not_hidden(payload) -> None:
    """A page that dropped them would look more complete than the database is."""
    assert payload["totals"]["skipped_unread"] == 1
    assert [n["notice_no"] for n in payload["skipped"]] == ["CN1097111"]


def test_the_totals_match_the_tenders_they_summarise(payload) -> None:
    totals = payload["totals"]
    decisions = [tender["decision"] for tender in payload["tenders"]]
    assert totals["scored"] == len(decisions)
    assert totals["go"] + totals["check"] + totals["no_go"] == len(decisions)


def test_the_file_says_where_it_came_from(payload) -> None:
    """Ground rule 1: a reader must be able to regenerate what the page shows."""
    assert payload["schema"] == SCHEMA_VERSION
    assert payload["generated_at"]
    assert payload["bidscout_version"]
    assert payload["source"]["database"] == "data/demo.sqlite3"
    assert payload["source"]["warehouse"].endswith("t.duckdb")
    assert "app.app_tenders" in payload["pipeline"]["marts"]


def test_every_landed_notice_is_accounted_for(payload) -> None:
    """The pipeline counts sum to what was landed: scored plus not read."""
    assert sum(payload["pipeline"]["read_status"].values()) == 3
    assert payload["pipeline"]["read_status"]["scored"] == payload["totals"]["scored"]


def test_an_unread_notice_says_why_it_was_not_read(payload) -> None:
    """A full contract notice with no Section 3 is waiting for `bidscout fetch`."""
    assert [n["read_status"] for n in payload["skipped"]] == ["awaiting fetch"]


def test_the_requirements_on_the_page_are_the_ones_the_scorer_stored(payload) -> None:
    """The marts model the scorer's output; they never re-read Section 3 themselves."""
    tender = {t["notice_no"]: t for t in payload["tenders"]}["CN1096282"]
    assert {r["kind"] for r in tender["requirements"]} >= {"turnover", "experience"}
    assert all(r["quote"] for r in tender["requirements"])


def test_the_export_command_writes_a_file_the_browser_can_parse(
    tmp_path, notice_item, section3_full, strong_profile
) -> None:
    import yaml

    db = tmp_path / "t.sqlite3"
    with Store(db) as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump(strong_profile), encoding="utf-8")
    out = tmp_path / "site" / "data.json"

    argv = ["--db", str(db), "--profile", str(profile), "export", "--out", str(out)]
    assert main(argv) == 0
    # strict=True rejects NaN and Infinity, exactly as a browser's JSON.parse does.
    assert json.loads(out.read_text(encoding="utf-8"), parse_constant=_reject)["tenders"]


def _reject(name: str) -> None:
    raise AssertionError(f"{name} is not valid JSON and a browser would refuse the file")


def test_the_committed_page_data_is_what_the_exporter_writes() -> None:
    """The published page must not drift from the code that produced it.

    This checks the shape of the committed file, not its contents: the numbers
    change whenever the demo is regenerated, but the keys the page reads, and
    the rule that no amount is a JSON number, must hold in the file that is
    actually served.
    """
    data = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    assert data["schema"] == SCHEMA_VERSION
    for key in ("generated_at", "source", "company", "rules", "totals", "tenders", "skipped"):
        assert key in data, f"site/data.json has no {key!r}; the page reads it"
    assert [value for value in _walk(data) if isinstance(value, float)] == []


def test_the_page_reads_the_schema_version_the_exporter_writes() -> None:
    """A page shipped against an older payload would render the wrong thing."""
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert f"const SCHEMA = {SCHEMA_VERSION};" in page


def test_the_page_never_writes_portal_text_as_html() -> None:
    """Titles and quotes come from a public portal; the page must not execute them.

    Guards the one habit that keeps that true. If innerHTML appears here, a
    tender title could carry markup onto a published page.
    """
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert re.search(r"\.innerHTML\s*=", page) is None
    assert "insertAdjacentHTML" not in page
    assert "document.write(" not in page
