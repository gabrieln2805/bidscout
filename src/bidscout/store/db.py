"""Read and write the SQLite database.

Nothing here deletes. A notice seen again updates ``last_seen`` and the raw
payload; it never replaces history. That is what lets the watcher tell "new"
from "seen before" without a second request to the portal.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from bidscout.models import Notice, Section3, Verdict
from bidscout.store.schema import SCHEMA

DEFAULT_DB_PATH = Path("data") / "bidscout.sqlite3"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    """A thin, explicit wrapper over one SQLite file."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ writes

    def save_notice(self, notice: Notice) -> bool:
        """Store a notice. Returns True the first time it is seen.

        The return value is what the watcher reports as "new". It comes from
        the database rather than from a comparison against the last poll, so
        a restart does not announce the whole market as new.
        """
        existing = self.connection.execute(
            "SELECT 1 FROM notices WHERE c_notice_id = ?", (notice.c_notice_id,)
        ).fetchone()
        now = _now()
        if existing:
            self.connection.execute(
                "UPDATE notices SET last_seen = ?, raw = ? WHERE c_notice_id = ?",
                (now, json.dumps(notice.raw, ensure_ascii=False), notice.c_notice_id),
            )
        else:
            self.connection.execute(
                """INSERT INTO notices (c_notice_id, notice_no, init_notice_id, title, buyer,
                       cpv, estimated_value_ron, published_at, deadline_at, notice_type_id,
                       first_seen, last_seen, raw)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    notice.c_notice_id,
                    notice.notice_no,
                    notice.init_notice_id,
                    notice.title,
                    notice.buyer,
                    notice.cpv,
                    str(notice.estimated_value_ron) if notice.estimated_value_ron else None,
                    notice.published_at,
                    notice.deadline_at,
                    notice.notice_type_id,
                    now,
                    now,
                    json.dumps(notice.raw, ensure_ascii=False),
                ),
            )
            if notice.buyer:
                self.connection.execute(
                    "INSERT OR IGNORE INTO buyers (name, first_seen) VALUES (?, ?)",
                    (notice.buyer, now),
                )
        self.connection.commit()
        return existing is None

    def save_section3(self, c_notice_id: str, raw: dict[str, Any]) -> None:
        """Store Section 3 exactly as the portal returned it."""
        self.connection.execute(
            """INSERT INTO sections (c_notice_id, fetched_at, section3_raw) VALUES (?,?,?)
               ON CONFLICT (c_notice_id) DO UPDATE SET
                   fetched_at = excluded.fetched_at,
                   section3_raw = excluded.section3_raw""",
            (c_notice_id, _now(), json.dumps(raw, ensure_ascii=False)),
        )
        self.connection.commit()

    def save_documents(self, c_notice_id: str, documents: Iterable[dict[str, str]]) -> int:
        """Store the file list for a notice. Returns how many rows were added."""
        rows = [
            (
                c_notice_id,
                doc.get("guid") or doc.get("noticeDocumentUrl", "").rsplit("/", 1)[-1],
                doc.get("noticeDocumentName", ""),
                doc.get("noticeDocumentCode"),
                doc.get("group"),
            )
            for doc in documents
        ]
        cursor = self.connection.executemany(
            """INSERT OR IGNORE INTO documents (c_notice_id, guid, name, code, doc_group)
               VALUES (?,?,?,?,?)""",
            rows,
        )
        self.connection.commit()
        return cursor.rowcount

    def save_verdict(self, c_notice_id: str, company: str, verdict: Verdict) -> None:
        """Store a verdict so the web page can read it without re-scoring."""
        self.connection.execute(
            """INSERT INTO scores (c_notice_id, company, decision, score, reasons,
                                   unresolved, scored_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT (c_notice_id, company) DO UPDATE SET
                   decision = excluded.decision, score = excluded.score,
                   reasons = excluded.reasons, unresolved = excluded.unresolved,
                   scored_at = excluded.scored_at""",
            (
                c_notice_id,
                company,
                verdict.decision.value,
                verdict.score,
                json.dumps(
                    [
                        {"text": r.text, "quote": r.quote, "source_field": r.source_field}
                        for r in verdict.reasons
                    ],
                    ensure_ascii=False,
                ),
                json.dumps(verdict.unresolved, ensure_ascii=False),
                _now(),
            ),
        )
        self.connection.commit()

    # ------------------------------------------------------------------- reads

    def notices(self, cpv_prefix: str | None = None) -> Iterator[Notice]:
        """Yield stored notices, newest first.

        ``cpv_prefix`` matches the **primary** CPV only. Secondary codes are
        not stored yet, so a notice whose IT code is secondary will be missed.
        The CLI prints this limit rather than hide it.
        """
        sql = "SELECT * FROM notices"
        params: tuple[Any, ...] = ()
        if cpv_prefix:
            sql += " WHERE cpv LIKE ?"
            params = (f"{cpv_prefix}%",)
        sql += " ORDER BY published_at DESC"
        for row in self.connection.execute(sql, params):
            yield _row_to_notice(row)

    def section3(self, c_notice_id: str) -> Section3 | None:
        """Return the stored Section 3, or None when the notice was never read."""
        row = self.connection.execute(
            "SELECT section3_raw FROM sections WHERE c_notice_id = ?", (c_notice_id,)
        ).fetchone()
        if row is None:
            return None
        return Section3(init_notice_id=c_notice_id, raw=json.loads(row["section3_raw"]))

    def counts(self) -> dict[str, int]:
        """Row counts, for ``bidscout stats``."""
        tables = ("notices", "buyers", "documents", "sections", "scores")
        return {
            table: int(
                self.connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in tables
        }


def _row_to_notice(row: sqlite3.Row) -> Notice:
    value = row["estimated_value_ron"]
    return Notice(
        c_notice_id=row["c_notice_id"],
        notice_no=row["notice_no"],
        init_notice_id=row["init_notice_id"],
        title=row["title"],
        buyer=row["buyer"],
        cpv=row["cpv"],
        estimated_value_ron=Decimal(value) if value else None,
        published_at=row["published_at"],
        deadline_at=row["deadline_at"],
        notice_type_id=row["notice_type_id"],
        raw=json.loads(row["raw"]),
    )
