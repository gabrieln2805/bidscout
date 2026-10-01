"""An existing database must keep working when a column is added.

The schema is applied with ``CREATE TABLE IF NOT EXISTS``, which does nothing
at all to a table that already exists. Without a migration step, a column
added to ``notices`` would be missing from every database written before it,
and the first query naming it would fail with "no such column" — on the one
machine that holds the real data.
"""

import sqlite3

from bidscout.pipeline import notice_from_item
from bidscout.store.db import Store
from bidscout.store.schema import ADDED_COLUMNS

#: ``notices`` exactly as it was before ``has_lots`` existed.
OLD_NOTICES_DDL = """
CREATE TABLE notices (
    c_notice_id         TEXT PRIMARY KEY,
    notice_no           TEXT NOT NULL,
    init_notice_id      TEXT,
    title               TEXT NOT NULL,
    buyer               TEXT,
    cpv                 TEXT,
    estimated_value_ron TEXT,
    published_at        TEXT,
    deadline_at         TEXT,
    notice_type_id      INTEGER,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    raw                 TEXT NOT NULL
);
"""


def _old_database(path) -> None:
    """Write one row the old way, with no ``has_lots`` column anywhere."""
    connection = sqlite3.connect(path)
    connection.executescript(OLD_NOTICES_DDL)
    connection.execute(
        """INSERT INTO notices (c_notice_id, notice_no, init_notice_id, title, buyer, cpv,
               estimated_value_ron, published_at, deadline_at, notice_type_id,
               first_seen, last_seen, raw)
           VALUES ('1096282','CN1096282','384463','Servicii',' COMUNA CHETANI','72000000',
               '1804000','2026-09-18T09:14:00Z','2026-10-20T15:00:00Z',2,
               '2026-09-18T10:00:00Z','2026-09-18T10:00:00Z','{}')""",
    )
    connection.commit()
    connection.close()


def test_a_database_written_before_the_column_still_opens(tmp_path, notice_item) -> None:
    db = tmp_path / "old.sqlite3"
    _old_database(db)
    with Store(db) as store:
        stored = next(store.notices())
        assert stored.c_notice_id == "1096282"
        # No value was ever written, so the honest default is "no lots known".
        assert stored.has_lots is False


def test_the_old_row_is_kept_rather_than_rebuilt(tmp_path, notice_item) -> None:
    """Ground rule 3: a migration adds a column, it never drops stored rows."""
    db = tmp_path / "old.sqlite3"
    _old_database(db)
    with Store(db) as store:
        assert store.counts()["notices"] == 1
        assert next(store.notices()).notice_no == "CN1096282"


def test_a_notice_can_still_be_written_to_a_migrated_database(tmp_path, notice_item) -> None:
    db = tmp_path / "old.sqlite3"
    _old_database(db)
    with Store(db) as store:
        assert store.save_notice(notice_from_item({**notice_item, "cNoticeId": 999,
                                                   "noticeNo": "CN999", "hasLots": True})) is True
        by_no = {notice.notice_no: notice for notice in store.notices()}
        assert by_no["CN999"].has_lots is True


def test_every_declared_migration_names_a_column_in_the_schema() -> None:
    """A stale entry here would silently stop migrating anything."""
    from bidscout.store.schema import SCHEMA

    for _table, column, ddl in ADDED_COLUMNS:
        assert column in SCHEMA, f"{column} is migrated but not in SCHEMA"
        assert ddl.startswith(column)
