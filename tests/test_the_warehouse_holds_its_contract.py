"""The warehouse is the app's data contract, and ``dbt build`` enforces it.

The page reads the ``app`` marts and nothing else, so these tests build the
real warehouse from a small landing database with the real ``dbt build`` and
look at what the marts say. Each build takes seconds; the read-only checks
share one.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from bidscout.decide.rules import load_profile, load_rules
from bidscout.models import Decision, Verdict
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store
from bidscout.warehouse import (
    WarehouseBuildFailed,
    read_app_marts,
    transform,
    warehouse_path_for,
)

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

#: The portal's "not found", as the 2 October run landed it.
NOT_FOUND = {"efCriteriaMin": None, "hasError": True, "responseMessage": "nu a fost gasit"}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _landing(path: Path) -> Path:
    """Four notices, one at each stage a notice can be at."""
    item = _fixture("notice_item.json")
    with Store(path) as store:
        # Read and scored.
        store.save_notice(notice_from_item(item))
        store.save_section3("1096282", _fixture("section3_cn1096282.json"))
        # The portal said "not found"; the CUI is written "RO 4305814 - ...".
        store.save_notice(notice_from_item({
            **item, "cNoticeId": 1096500, "noticeNo": "CN1096500",
            "contractingAuthorityNameAndFN": "RO 4305814 - COMUNA CHETANI",
        }))
        store.save_section3("1096500", NOT_FOUND)
        # Waiting for `bidscout fetch`, same buyer written another way.
        store.save_notice(notice_from_item({
            **item, "cNoticeId": 1096600, "noticeNo": "CN1096600",
            "contractingAuthorityNameAndFN": "4305814 - Comuna Chetani",
        }))
        # A simplified notice: nothing can read it yet.
        store.save_notice(notice_from_item({
            **item, "cNoticeId": 1096700, "noticeNo": "SCN1096700", "sysNoticeTypeId": 17,
        }))
        profile = load_profile(ROOT / "config" / "profile.example.yaml")
        score_stored(store, profile, load_rules(ROOT / "config" / "rules" / "it.yaml"))
    return path


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    landing = _landing(tmp_path_factory.mktemp("wh") / "store.sqlite3")
    return transform(landing, company="Example SRL")


def test_the_warehouse_sits_beside_its_landing_file(built) -> None:
    assert built.name == "store.duckdb"
    assert warehouse_path_for("data/demo.sqlite3") == Path("data/demo.duckdb")


def test_every_landed_notice_is_one_app_row_with_its_stage(built) -> None:
    rows = {row["notice_no"]: row for row in read_app_marts(built)["app_tenders"]}
    assert {no: row["read_status"] for no, row in rows.items()} == {
        "CN1096282": "scored",
        "CN1096500": "portal refused",
        "CN1096600": "awaiting fetch",
        "SCN1096700": "no known endpoint",
    }


def test_only_a_scored_notice_carries_a_decision(built) -> None:
    """Ground rule 2 at the warehouse boundary, held by a dbt test too."""
    for row in read_app_marts(built)["app_tenders"]:
        assert (row["decision"] is not None) == (row["read_status"] == "scored")


def test_one_buyer_however_its_fiscal_code_is_written(built) -> None:
    """"RO 4305814", "4305814" — the same CUI, so one row in dim_buyers."""
    connection = duckdb.connect(str(built), read_only=True)
    try:
        keys = connection.execute(
            "select buyer_key, notices from core.dim_buyers where buyer_key = '4305814'"
        ).fetchall()
    finally:
        connection.close()
    assert keys == [("4305814", 2)]


def test_money_leaves_the_warehouse_as_decimal_never_float(built) -> None:
    marts = read_app_marts(built)
    values = [row["estimated_value_ron"] for row in marts["app_tenders"]]
    assert values and not any(isinstance(value, float) for value in values)
    assert all(isinstance(r["amount_text"], str | None) for r in marts["app_tender_requirements"])


def test_a_broken_contract_stops_the_build(tmp_path) -> None:
    """A decision outside GO / CHECK / NO-GO fails a data test, so nothing is published."""
    landing = _landing(tmp_path / "store.sqlite3")
    with Store(landing) as store:
        store.save_verdict("1096282", "Example SRL", Verdict(Decision.GO, 90))
        store.connection.execute("UPDATE scores SET decision = 'MAYBE'")
        store.connection.commit()
    with pytest.raises(WarehouseBuildFailed, match="accepted_values"):
        transform(landing, company="Example SRL")


def test_a_missing_landing_file_is_named(tmp_path) -> None:
    with pytest.raises(WarehouseBuildFailed, match="no landing database"):
        transform(tmp_path / "nowhere.sqlite3")
