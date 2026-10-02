"""The file list arrives as groups, and the groups are not a fixed list.

``GetDfNoticeSectionFiles`` answers with an object whose keys are groups:
``dfNoticeDocs``, ``duaeDocs``, ``contractingStrategyDocs``, ``decisionDocs``,
``exAnteDocs``. Reading only those five would mean a group the portal adds
later is dropped in silence — and a newly added group is likely to be exactly
the one carrying a clarification that changes a deadline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bidscout.fetch import document_rows, fetch_missing, format_fetch_report
from bidscout.pipeline import notice_from_item
from bidscout.sicap.client import SicapClient
from bidscout.store.db import Store

FIXTURES = Path(__file__).parent / "fixtures"


def _documents() -> dict[str, Any]:
    return json.loads((FIXTURES / "documents_cn1096282.json").read_text(encoding="utf-8"))


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.content = b""

    def json(self) -> Any:
        return self._payload


class _Portal:
    def __init__(self, section: dict[str, Any], documents: Any) -> None:
        self.section = section
        self.documents = documents
        self.document_calls = 0

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if "GetSection3View" in url:
            return _Response(self.section)
        if "GetDfNoticeSectionFiles" in url:
            self.document_calls += 1
            if isinstance(self.documents, Exception):
                raise self.documents
            return _Response(self.documents)
        raise AssertionError(url)

    def post(self, url: str, json: dict[str, Any] | None = None) -> Any:
        raise AssertionError("fetch must never run a search")


# ------------------------------------------------------------------ flattening


def test_every_group_is_read_not_only_the_five_we_know() -> None:
    payload = dict(_documents())
    payload["clarificationDocs"] = [
        {
            "noticeDocumentUrl": "api-pub/files/noticedoc/aaaa1111bbbb2222cccc3333dddd4444",
            "noticeDocumentName": "Raspuns clarificare 1.pdf",
            "noticeDocumentCode": "CN1096282/00009",
        }
    ]
    rows, unusable = document_rows(payload)
    assert unusable == 0
    assert {row["group"] for row in rows} == {
        "dfNoticeDocs",
        "duaeDocs",
        "clarificationDocs",
    }


def test_the_guid_is_the_tail_of_the_url() -> None:
    """The portal gives a path; the database keys on the GUID at the end of it."""
    rows, _ = document_rows(_documents())
    assert "28c82dc9e28547f795cc5ac9553e5a35" in {row["guid"] for row in rows}


def test_an_empty_or_null_group_is_not_an_error() -> None:
    """``decisionDocs: null`` and ``exAnteDocs: []`` are both normal."""
    rows, unusable = document_rows(_documents())
    assert len(rows) == 3
    assert unusable == 0


def test_an_entry_with_no_url_is_counted_rather_than_given_an_empty_key() -> None:
    """Two keyless rows would collide, and ``INSERT OR IGNORE`` would eat one.

    ``documents`` is keyed on (notice, guid). An entry with neither a URL nor a
    GUID would be stored under the empty string, so the second such entry on
    the same notice would silently vanish — and nobody would know a file had
    been lost rather than never offered.
    """
    rows, unusable = document_rows(
        {
            "dfNoticeDocs": [
                {"noticeDocumentName": "Anexa fara link.pdf"},
                {"noticeDocumentName": "A doua anexa fara link.pdf"},
            ]
        }
    )
    assert rows == []
    assert unusable == 2


def test_a_payload_that_is_not_groups_at_all_yields_nothing() -> None:
    assert document_rows(None) == ([], 0)
    assert document_rows({"total": 3, "message": "none"}) == ([], 0)


# ------------------------------------------------------------------- in a run


def test_the_file_list_is_stored_beside_the_section(tmp_path, notice_item, section3_full) -> None:
    portal = _Portal(section3_full.raw, _documents())
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        run = fetch_missing(store, SicapClient(transport=portal, pause_seconds=0.0))
        assert store.counts()["documents"] == 3
    assert run.documents_stored == 3


def test_a_second_run_adds_no_duplicate_rows(tmp_path, notice_item, section3_full) -> None:
    """Keyed on the GUID, which never changes, so a re-poll is free."""
    portal = _Portal(section3_full.raw, _documents())
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        client = SicapClient(transport=portal, pause_seconds=0.0)
        fetch_missing(store, client)
        # The notice is read now, so fetch would not revisit it; store the same
        # list again directly to prove the key, not the queue.
        rows, _ = document_rows(_documents())
        store.save_documents("1096282", rows)
        assert store.counts()["documents"] == 3


def test_a_missing_file_list_does_not_unstore_the_section(
    tmp_path, notice_item, section3_full
) -> None:
    """The section is what makes a notice scorable; the files are a bonus.

    So the section is written first and kept, and the failed file list is
    reported rather than rolled back into "this notice was not read".
    """
    from bidscout.errors import NoticeNotFound

    portal = _Portal(section3_full.raw, NoticeNotFound("no files for initNoticeId=384463"))
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        run = fetch_missing(store, SicapClient(transport=portal, pause_seconds=0.0))
        assert store.section3("1096282") is not None
    assert run.fetched == ["CN1096282"]
    assert [label for label, _ in run.documents_failed] == ["CN1096282"]
    assert "file list did not come" in format_fetch_report(run)


def test_a_notice_the_portal_refused_costs_no_file_list_request(
    tmp_path, notice_item
) -> None:
    """No section came back at all, so there is no point asking for its files."""
    from bidscout.errors import NoticeNotFound

    class _Refusing:
        def __init__(self) -> None:
            self.document_calls = 0

        def get(self, url: str, params: Any = None) -> Any:
            if "GetSection3View" in url:
                raise NoticeNotFound("no Section 3 for initNoticeId=384463")
            self.document_calls += 1
            return _Response({})

        def post(self, url: str, json: Any = None) -> Any:
            raise AssertionError("fetch must never run a search")

    portal = _Refusing()
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        fetch_missing(store, SicapClient(transport=portal, pause_seconds=0.0))
    assert portal.document_calls == 0


def test_a_document_field_of_the_wrong_shape_does_not_reach_sqlite(
    tmp_path, notice_item, section3_full
) -> None:
    """SQLite refuses to bind a dict, and the error lands far from its cause.

    Every field out of the portal is forced to a string for that reason: a
    ``noticeDocumentCode`` that arrived as an object would otherwise abort the
    whole run after the section had already been stored.
    """
    payload = {
        "dfNoticeDocs": [
            {
                "noticeDocumentUrl": "api-pub/files/noticedoc/" + "a" * 32,
                "noticeDocumentName": {"ro": "Caiet de sarcini.pdf"},
                "noticeDocumentCode": ["CN1096282/00003"],
            }
        ]
    }
    portal = _Portal(section3_full.raw, payload)
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        run = fetch_missing(store, SicapClient(transport=portal, pause_seconds=0.0))
        assert store.counts()["documents"] == 1
    assert run.documents_stored == 1


def test_a_code_that_is_missing_stays_null_rather_than_an_empty_string() -> None:
    """The column is nullable; "" would read as a code the buyer gave."""
    rows, _ = document_rows(
        {"dfNoticeDocs": [{"noticeDocumentUrl": "api-pub/files/noticedoc/" + "b" * 32}]}
    )
    assert rows[0]["noticeDocumentCode"] is None
