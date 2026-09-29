"""Ground rule 3: the raw payload is a column, and nothing deletes it."""

import json

from bidscout.pipeline import notice_from_item
from bidscout.store.db import Store


def test_a_notice_is_new_only_the_first_time(tmp_path, notice_item) -> None:
    """The watcher reports "new" from the database, so a restart is quiet."""
    with Store(tmp_path / "t.sqlite3") as store:
        notice = notice_from_item(notice_item)
        assert store.save_notice(notice) is True
        assert store.save_notice(notice) is False


def test_the_whole_portal_item_survives_a_round_trip(tmp_path, notice_item) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        stored = next(store.notices())
        assert stored.raw == notice_item
        assert stored.raw["procedureId"] == 200111


def test_section3_is_stored_verbatim(tmp_path, notice_item, section3_full) -> None:
    """A parser rewrite is replayed from this column, never re-downloaded."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        assert store.section3("1096282").raw == section3_full.raw


def test_refetching_section3_replaces_it_without_losing_the_notice(
    tmp_path, notice_item, section3_full
) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        store.save_section3("1096282", {"efCriteriaMin": "changed"})
        assert store.section3("1096282").raw == {"efCriteriaMin": "changed"}
        assert store.counts()["notices"] == 1


def test_a_buyer_is_recorded_once(tmp_path, notice_item) -> None:
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_notice(notice_from_item({**notice_item, "cNoticeId": 999, "noticeNo": "CN999"}))
        assert store.counts()["buyers"] == 1
        assert store.counts()["notices"] == 2


def test_documents_are_keyed_by_guid_so_a_repoll_adds_nothing(tmp_path, notice_item) -> None:
    docs = [
        {
            "noticeDocumentUrl": "api-pub/files/noticedoc/28c82dc9e28547f795cc5ac9553e5a35",
            "noticeDocumentName": "Caiet de sarcini.pdf",
            "noticeDocumentCode": "CN1096282/00003",
            "group": "dfNoticeDocs",
        }
    ]
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_documents("1096282", docs)
        store.save_documents("1096282", docs)
        assert store.counts()["documents"] == 1


def test_a_verdict_is_saved_as_json_a_web_page_can_read(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    from bidscout.decide.engine import decide
    from bidscout.extract.gates import extract_requirements

    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        verdict = decide(extract_requirements(section3_full), strong_profile, rules)
        store.save_verdict("1096282", "Strong SRL", verdict)
        row = store.connection.execute("SELECT reasons FROM scores").fetchone()
        assert isinstance(json.loads(row["reasons"]), list)
