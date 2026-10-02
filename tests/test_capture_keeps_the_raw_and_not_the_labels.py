"""`bidscout capture` writes the payload and leaves the judgement to a person."""

from __future__ import annotations

import json
from typing import Any

import pytest

from bidscout.accuracy.capture import capture_case
from bidscout.accuracy.cases import load_case
from bidscout.errors import SectionNotStored
from bidscout.pipeline import notice_from_item
from bidscout.store.db import Store


class FakeSection3Source:
    """Stands in for ``SicapClient`` so this test opens no socket."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.asked_for: list[str] = []

    def get_section3(self, init_notice_id: int | str) -> dict[str, Any]:
        self.asked_for.append(str(init_notice_id))
        return self.payload


@pytest.fixture
def store_with_section(tmp_path, notice_item, section3_full):
    store = Store(tmp_path / "t.sqlite3")
    store.save_notice(notice_from_item(notice_item))
    store.save_section3("1096282", section3_full.raw)
    yield store
    store.close()


def test_a_captured_case_is_written_unlabelled(store_with_section, tmp_path, section3_full):
    """A capture must never guess the labels: the whole harness rests on them."""
    path = capture_case(store_with_section, "1096282", tmp_path / "cases")
    body = json.loads(path.read_text(encoding="utf-8"))

    assert body["labelled"] is False
    assert all(entry["amount"] is None for entry in body["labels"].values())
    assert body["section3_raw"] == section3_full.raw


def test_a_captured_case_is_named_after_the_notice_number(store_with_section, tmp_path):
    path = capture_case(store_with_section, "1096282", tmp_path / "cases")
    assert path.name == "cn1096282.json"


def test_a_captured_case_reloads_through_the_same_reader(store_with_section, tmp_path):
    """Written and read by the same format, so a capture is usable immediately."""
    path = capture_case(store_with_section, "1096282", tmp_path / "cases")
    case = load_case(path)
    assert case.labelled is False
    assert case.section3.text("efCriteriaMin")


def test_capturing_a_notice_we_have_not_read_says_so(tmp_path, notice_item):
    """Better than an empty case file, which looks like a buyer who asks for nothing."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        with pytest.raises(SectionNotStored, match="no Section 3 stored"):
            capture_case(store, "1096282", tmp_path / "cases")


def test_a_live_capture_stores_the_raw_before_anything_reads_it(tmp_path, notice_item):
    """Ground rule 3: the payload reaches the database, not only the case file."""
    payload = {"efCriteriaMin": "<p>minimum <b>900.000,00 lei</b></p>"}
    source = FakeSection3Source(payload)
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        capture_case(store, "1096282", tmp_path / "cases", client=source)
        stored = store.section3("1096282")

    assert stored is not None
    assert stored.raw == payload
    # Section 3 is keyed by the cNoticeId, not the noticeId (384463).
    assert source.asked_for == ["1096282"]


def test_a_live_capture_of_an_unknown_notice_falls_back_to_the_id_given(tmp_path):
    """A notice that is not in the database is asked for by the id the user typed."""
    source = FakeSection3Source({"efCriteriaMin": "<p>x</p>"})
    with Store(tmp_path / "t.sqlite3") as store:
        capture_case(store, "555000", tmp_path / "cases", client=source)
    assert source.asked_for == ["555000"]
