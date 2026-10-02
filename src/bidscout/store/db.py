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

from bidscout.models import Confidence, Notice, Requirement, Section3, Verdict
from bidscout.store.schema import ADDED_COLUMNS, SCHEMA

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
        self._add_missing_columns()
        self.connection.commit()

    def _add_missing_columns(self) -> None:
        """Bring a database written by an older version up to today's columns.

        ``CREATE TABLE IF NOT EXISTS`` does nothing to a table that already
        exists, so a new column never reaches an existing file on its own and
        the first query naming it fails with "no such column". Adding instead
        of recreating is deliberate: ground rule 3 means no stored row is ever
        thrown away to simplify a migration.
        """
        for table, column, ddl in ADDED_COLUMNS:
            present = {
                row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")
            }
            if present and column not in present:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

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
            # ``has_lots`` is refreshed, unlike the other convenience columns,
            # because it changes the verdict: a corrigendum that splits a tender
            # into lots must not leave yesterday's GO standing on a figure that
            # now belongs to the whole tender rather than to one lot.
            self.connection.execute(
                "UPDATE notices SET last_seen = ?, raw = ?, has_lots = ? WHERE c_notice_id = ?",
                (
                    now,
                    json.dumps(notice.raw, ensure_ascii=False),
                    int(notice.has_lots),
                    notice.c_notice_id,
                ),
            )
        else:
            self.connection.execute(
                """INSERT INTO notices (c_notice_id, notice_no, init_notice_id, title, buyer,
                       cpv, estimated_value_ron, published_at, deadline_at, notice_type_id,
                       has_lots, first_seen, last_seen, raw)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                    int(notice.has_lots),
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

    def save_requirements(self, c_notice_id: str, requirements: Iterable[Requirement]) -> int:
        """Store what the extractor read, with the buyer's sentence beside it.

        This is a trace, not a cache. The scorer still re-reads
        ``sections.section3_raw`` on every run, so a fix to the extractor
        applies immediately; these rows only answer "which sentences produced
        the verdict I am looking at" without re-running the parser.

        The rows for a notice are replaced, because a second extraction of the
        same Section 3 supersedes the first. Nothing is lost by that: the raw
        section it was read from is still on file (ground rule 3).

        ``amount`` goes in as ``str``, never as a float. SQLite would store a
        float and hand back 2699999.9999999995 for a sum the buyer wrote out
        exactly.
        """
        self.connection.execute("DELETE FROM requirements WHERE c_notice_id = ?", (c_notice_id,))
        now = _now()
        rows = [
            (
                c_notice_id,
                req.kind,
                str(req.amount) if req.amount is not None else None,
                req.currency,
                req.quote,
                req.source_field,
                req.confidence.value,
                now,
            )
            for req in requirements
        ]
        self.connection.executemany(
            """INSERT INTO requirements (c_notice_id, kind, amount, currency, quote,
                                         source_field, confidence, extracted_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )
        self.connection.commit()
        return len(rows)

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
                        {
                            "text": r.text,
                            "quote": r.quote,
                            "source_field": r.source_field,
                            "outcome": r.outcome,
                        }
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

    #: A notice is simplified when the portal marks it type 17 or numbers it
    #: SCN…. No detail endpoint is known for either, so nothing can read one.
    _SIMPLIFIED = "(n.notice_type_id = 17 OR UPPER(n.notice_no) LIKE 'SCN%')"

    #: Stored notices with no row in ``sections`` — the ones nobody has read.
    _MISSING_SECTION3 = """FROM notices n
                           LEFT JOIN sections s ON s.c_notice_id = n.c_notice_id
                           WHERE s.c_notice_id IS NULL"""

    def notices_missing_section3(
        self, limit: int | None = None, exclude_simplified: bool = False
    ) -> Iterator[Notice]:
        """Yield stored notices that have no Section 3, newest first.

        With ``exclude_simplified`` left False this is the exact complement of
        what an unfiltered ``score_stored`` skips and counts: a notice appears
        here precisely because the scorer refuses to touch it.

        ``exclude_simplified`` is what ``fetch`` uses, and it has to filter in
        SQL rather than in the loop. Simplified notices can never be fetched,
        so they never leave the queue; counted against ``limit`` they would sit
        at the front of every run for ever and starve the notices that can
        actually be read — 60% of what the portal publishes blocking the other
        40%.

        Newest first because a tender published today has a deadline worth
        catching, while one from six weeks ago may already have closed.
        """
        sql = f"SELECT n.* {self._MISSING_SECTION3}"
        if exclude_simplified:
            sql += f" AND NOT {self._SIMPLIFIED}"
        sql += " ORDER BY n.published_at DESC"
        params: tuple[Any, ...] = ()
        if limit is not None:
            # Guarded rather than passed through: SQLite reads a negative LIMIT
            # as no limit at all, so a caller's off-by-one would quietly turn a
            # bounded run into a run over the whole database.
            if limit < 0:
                raise ValueError(f"limit must not be negative, got {limit}")
            sql += " LIMIT ?"
            params = (limit,)
        for row in self.connection.execute(sql, params):
            yield _row_to_notice(row)

    def count_missing_section3(
        self, exclude_simplified: bool = False, simplified_only: bool = False
    ) -> int:
        """How many stored notices have no Section 3.

        Counted in SQL rather than by walking ``notices_missing_section3``,
        because the caller wants a number and the rows carry a raw JSON column
        each. ``simplified_only`` answers the opposite question: how large the
        backlog is that no command can currently read.
        """
        sql = f"SELECT COUNT(*) AS n {self._MISSING_SECTION3}"
        if simplified_only:
            sql += f" AND {self._SIMPLIFIED}"
        elif exclude_simplified:
            sql += f" AND NOT {self._SIMPLIFIED}"
        return int(self.connection.execute(sql).fetchone()["n"])

    def section3(self, c_notice_id: str) -> Section3 | None:
        """Return the stored Section 3, or None when the notice was never read."""
        row = self.connection.execute(
            "SELECT section3_raw FROM sections WHERE c_notice_id = ?", (c_notice_id,)
        ).fetchone()
        if row is None:
            return None
        return Section3(init_notice_id=c_notice_id, raw=json.loads(row["section3_raw"]))

    def requirements(self, c_notice_id: str) -> list[Requirement]:
        """Return the stored requirements for one notice, newest extraction first.

        An empty list means nobody has scored this notice yet, which is a
        different thing from a buyer who asks for nothing. The caller is
        expected to say which of the two it is rather than print "no
        requirements" for both.
        """
        rows = self.connection.execute(
            """SELECT kind, amount, currency, quote, source_field, confidence
               FROM requirements WHERE c_notice_id = ? ORDER BY kind""",
            (c_notice_id,),
        ).fetchall()
        return [
            Requirement(
                kind=row["kind"],
                amount=Decimal(row["amount"]) if row["amount"] is not None else None,
                currency=row["currency"],
                quote=row["quote"],
                source_field=row["source_field"],
                confidence=Confidence(row["confidence"]),
            )
            for row in rows
        ]

    def requirements_extracted_at(self, c_notice_id: str) -> str | None:
        """When these requirements were read, so a stale trace can be spotted."""
        row = self.connection.execute(
            "SELECT MAX(extracted_at) AS when_ FROM requirements WHERE c_notice_id = ?",
            (c_notice_id,),
        ).fetchone()
        return row["when_"] if row else None

    def counts(self) -> dict[str, int]:
        """Row counts, for ``bidscout stats``."""
        tables = ("notices", "buyers", "documents", "sections", "requirements", "scores")
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
        has_lots=bool(row["has_lots"]),
        raw=json.loads(row["raw"]),
    )
