"""Fill the gap between ``watch`` and ``score``.

``watch`` stores what the search results carry, and the search results carry
no requirements at all: no Section 3, no file list. The scorer then skips
every one of those notices, correctly and deliberately, so a database filled
by ``watch`` alone answers nothing. This module is the missing step: for every
stored notice with no Section 3, pull the section and the document list and
store both.

Three rules shape everything below.

*Store what arrived, exactly as it arrived.* Ground rule 3. Whatever the
portal answers is written to ``sections.section3_raw`` before anything reads
it, including a payload the reader cannot make sense of — that is the row a
later parser fix is replayed from. The danger such a payload used to carry,
that an unreadable section scores GO because every gate reads "the buyer does
not ask for one", is held where it belongs: ``decide`` now returns CHECK when
it recognised nothing in a section. Refusing to store the payload here was the
wrong place for that guard, and it left the notice to be re-requested on every
future run.

*Ask only what is worth asking.* A notice already read is not in the queue, so
a second run makes no request for it. Simplified notices are left out of the
queue entirely rather than attempted and skipped: no detail endpoint is known
for them, and counting them against ``--limit`` would let 60% of the market
starve the 40% that can actually be read.

*One notice's trouble is not the run's.* The portal refusing one notice is
recorded and the run moves on, because the next forty-nine are still worth
having. An unexpected failure is deliberately **not** caught: repeating it
once per notice would be fifty pointless requests to somebody else's server,
and every notice fetched before it is already committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from bidscout.errors import BidscoutError
from bidscout.models import Notice
from bidscout.store.db import Store


class NoticeReader(Protocol):
    """The two methods of ``SicapClient`` that fetching needs.

    Narrowed to a protocol for the same reason as everywhere else in this
    project: a test hands in a fake, ``requests`` is never imported, and the
    whole suite runs with the portal unreachable.
    """

    def get_section3(self, c_notice_id: int | str) -> dict[str, Any]: ...

    def get_documents(self, c_notice_id: int | str) -> dict[str, Any]: ...


@dataclass
class FetchRun:
    """What one pass of ``fetch`` did, and what it could not do.

    The lists hold notice numbers rather than counts, because ground rule 1
    means Gabriel has to be able to go and look at the ones they name.
    """

    #: Notices whose Section 3 is now on file and which ``score`` will read.
    fetched: list[str] = field(default_factory=list)
    #: (notice number, what the portal said). The run carried on past these.
    failed: list[tuple[str, str]] = field(default_factory=list)
    #: File-list rows added across the whole run.
    documents_stored: int = 0
    #: Notices whose Section 3 arrived but whose file list did not. The notice
    #: is scorable anyway; only the attachments are missing.
    documents_failed: list[tuple[str, str]] = field(default_factory=list)
    #: Entries in a file list with no URL and no GUID, so nothing to download
    #: and no key to store them under. Counted so they are not invisible.
    documents_without_guid: int = 0
    #: Simplified notices sitting in the database with no Section 3. Not part
    #: of this run at all — reported because they are a large and growing
    #: backlog that no command can currently touch.
    simplified_waiting: int = 0

    @property
    def considered(self) -> int:
        """How many notices this run actually asked the portal about."""
        return len(self.fetched) + len(self.failed)


def document_rows(payload: dict[str, Any] | None) -> tuple[list[dict[str, str | None]], int]:
    """Flatten the portal's grouped file list into rows, and count the unusable.

    The response is an object of groups (``dfNoticeDocs``, ``duaeDocs`` and
    the rest). Every key whose value is a list is treated as a group, rather
    than only the five groups named in docs/data-sources.md: a group the
    portal adds later would otherwise be dropped in silence, and a new
    clarification is exactly the file we would most want to have kept.

    An entry with neither a URL nor a GUID is left out and counted. It cannot
    be downloaded, and storing it would give it the empty string as its key —
    where the second such entry on the same notice would collide with the
    first and be swallowed by ``INSERT OR IGNORE``.

    Every value is forced to ``str``. A field that arrived as a list or an
    object would otherwise reach SQLite, which refuses to bind it and raises
    an error far away from the portal response that caused it.
    """
    rows: list[dict[str, str | None]] = []
    unusable = 0
    for group, entries in (payload or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            guid = _text(entry.get("guid"))
            if not guid:
                url = _text(entry.get("noticeDocumentUrl"))
                guid = url.rsplit("/", 1)[-1] if url else ""
            if not guid:
                unusable += 1
                continue
            rows.append(
                {
                    "guid": guid,
                    "noticeDocumentName": _text(entry.get("noticeDocumentName")),
                    "noticeDocumentCode": _text(entry.get("noticeDocumentCode")) or None,
                    "group": str(group),
                }
            )
    return rows, unusable


def _text(value: Any) -> str:
    """One portal field as a trimmed string, whatever shape it arrived in."""
    return "" if value is None else str(value).strip()


def fetch_missing(
    store: Store,
    client: NoticeReader,
    limit: int | None = None,
) -> FetchRun:
    """Read Section 3 and the file list for every stored notice that has neither.

    Newest first, like every other read in the store: a tender published today
    has a deadline worth catching, and one from six weeks ago may well have
    closed. ``limit`` bounds a single run so that a first pass over a large
    database is a series of polite visits rather than one long one.

    Nothing here deletes a stored section. A notice already read is not in the
    queue, so a second run with nothing new to do makes no request at all.
    """
    run = FetchRun(simplified_waiting=store.count_missing_section3(simplified_only=True))
    for notice in store.notices_missing_section3(limit=limit, exclude_simplified=True):
        _fetch_one(store, client, notice, notice.notice_no or notice.c_notice_id, run)
    return run


def _fetch_one(
    store: Store,
    client: NoticeReader,
    notice: Notice,
    label: str,
    run: FetchRun,
) -> None:
    """Fetch one notice's section and files, recording whatever happened."""
    # Both endpoints take the cNoticeId, although the parameter is called
    # ``initNoticeId``. Settled live on 2 October 2026; see
    # ``SicapClient.get_section3``. Sending the noticeId was the first live
    # bug: the portal answers "not found" with HTTP 200.
    try:
        raw = client.get_section3(notice.c_notice_id)
    except BidscoutError as exc:
        run.failed.append((label, str(exc)))
        return

    # Stored before anything reads it (ground rule 3), and stored under the
    # cNoticeId, which is the key the rest of the database uses. A payload the
    # reader cannot parse is stored too: ``decide`` holds such a notice at
    # CHECK, and this row is what a later parser fix is replayed from.
    store.save_section3(notice.c_notice_id, raw if isinstance(raw, dict) else {})
    run.fetched.append(label)

    try:
        payload = client.get_documents(notice.c_notice_id)
    except BidscoutError as exc:
        run.documents_failed.append((label, str(exc)))
        return

    rows, unusable = document_rows(payload)
    run.documents_without_guid += unusable
    if rows:
        run.documents_stored += store.save_documents(notice.c_notice_id, rows)


def format_fetch_report(run: FetchRun) -> str:
    """One readable block saying what was stored and what was not, and why.

    Every refusal names the notices behind it. A line that said only "3 failed"
    would be a claim Gabriel cannot check, which ground rule 1 forbids.
    """
    lines = [
        f"Section 3 is now on file for {len(run.fetched)} of {run.considered} "
        f"{_plural(run.considered, 'notice', 'notices')}, with {run.documents_stored} "
        f"new file-list {_plural(run.documents_stored, 'row', 'rows')}."
    ]
    for label, message in run.failed:
        lines.append(f"  {label}: {message}")
    for label, message in run.documents_failed:
        lines.append(f"  {label}: Section 3 stored, but the file list did not come: {message}")
    if run.documents_without_guid:
        count = run.documents_without_guid
        lines.append(
            f"  {count} file-list {_plural(count, 'entry', 'entries')} had no URL and no "
            f"GUID, so there was nothing to download and nothing to store "
            f"{_plural(count, 'it', 'them')} under."
        )
    if run.simplified_waiting:
        count = run.simplified_waiting
        lines.append(
            f"  {count} simplified {_plural(count, 'notice', 'notices')} in the database "
            f"{_plural(count, 'has', 'have')} no Section 3 and {_plural(count, 'was', 'were')} "
            "not asked for: no detail endpoint is known for them yet "
            "(docs/data-sources.md, open item 1)."
        )
    if run.fetched:
        lines.append("")
        lines.append("Run `bidscout score` to rank what has just been read.")
    return "\n".join(lines)


def _plural(count: int, one: str, many: str) -> str:
    """Pick the word that matches ``count``.

    Worth the four lines: this report is the only face ``fetch`` has, and
    "1 simplified notices" reads like a tool nobody checked.
    """
    return one if count == 1 else many
