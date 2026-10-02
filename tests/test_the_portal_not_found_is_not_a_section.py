"""The portal says "not found" with HTTP 200, dressed as a Section 3.

Found on the first live run, 2 October 2026. Asked with the wrong id, the
portal answered ``hasError: true`` and "Anuntul cautat nu a fost gasit in
sistem" inside a payload whose every criterion field was null. ``fetch`` stored
it as the notice's Section 3, which took the notice out of the queue for good
and left a row that reads like a buyer who asks for nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from bidscout.errors import NoticeNotFound
from bidscout.fetch import fetch_missing
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.sicap.client import SicapClient, is_error_payload
from bidscout.store.db import Store

#: Shortened from the real answer for CN1097018, asked by its noticeId.
NOT_FOUND: dict[str, Any] = {
    "personalSituation": None,
    "efCriteriaMin": None,
    "tpCriteriaQAStandardMin": None,
    "hasError": True,
    "responseMessage": "Anuntul cautat nu a fost gasit in sistem",
}

#: What the file-list endpoint answered for the same wrong id.
FILE_LIST_ERROR = [
    "Eroare de sistem 261002-D7",
    "Object reference not set to an instance of an object.",
]


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _Answers:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return _Response(self.payload)

    def post(self, url: str, json: dict[str, Any] | None = None) -> Any:
        raise AssertionError("no search here")


def _client(payload: Any) -> SicapClient:
    return SicapClient(transport=_Answers(payload), pause_seconds=0.0)


def test_the_client_raises_the_portals_own_words() -> None:
    with pytest.raises(NoticeNotFound, match="nu a fost gasit"):
        _client(NOT_FOUND).get_section3("101402981")


def test_a_file_list_that_is_a_list_of_errors_is_refused() -> None:
    with pytest.raises(NoticeNotFound, match="Eroare de sistem"):
        _client(FILE_LIST_ERROR).get_documents("101402981")


def test_a_real_section_is_not_mistaken_for_an_error(section3_full) -> None:
    assert not is_error_payload(section3_full.raw)
    assert not is_error_payload({"dfNoticeDocs": [], "isPubOrSu": True})


def test_fetch_records_the_refusal_and_stores_nothing(tmp_path, notice_item) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        run = fetch_missing(store, _client(NOT_FOUND))
        assert store.counts()["sections"] == 0
        assert store.count_missing_section3() == 1
    assert run.fetched == []
    assert "nu a fost gasit" in run.failed[0][1]


def test_an_error_row_already_on_disk_is_requeued_and_never_scored(
    tmp_path, notice_item, strong_profile, rules
) -> None:
    """The row the 2 October run left behind: kept, not read, asked for again."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", NOT_FOUND)

        assert store.section3("1096282") is None
        assert [n.c_notice_id for n in store.notices_missing_section3()] == ["1096282"]
        run = score_stored(store, strong_profile, rules)
        assert run.scored == 0
        assert [n.c_notice_id for n in run.skipped_unread] == ["1096282"]
