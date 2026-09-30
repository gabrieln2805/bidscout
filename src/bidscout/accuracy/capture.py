"""Turn one real notice into a case file the accuracy harness can measure.

The harness is only as honest as its input, so capturing has to be one
command rather than a hand-copy: a Section 3 that took effort to save is a
Section 3 that gets summarised instead of stored.

Two sources, on purpose. By default the payload comes from the local
database, which needs no network and can therefore be tested offline. With a
client it comes from the portal, and it is written to the database on the way
past — ground rule 3: the raw payload is kept before anything reads it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from bidscout.accuracy.cases import DEFAULT_CASE_DIR, write_case
from bidscout.errors import SectionNotStored
from bidscout.store.db import Store


class Section3Source(Protocol):
    """The one method of ``SicapClient`` that capturing needs.

    Narrowing it to this keeps ``requests`` out of the offline tests and lets
    a test hand in a fake without building a client at all.
    """

    def get_section3(self, init_notice_id: int | str) -> dict[str, Any]: ...


def capture_case(
    store: Store,
    c_notice_id: str,
    directory: str | Path = DEFAULT_CASE_DIR,
    client: Section3Source | None = None,
) -> Path:
    """Write an unlabelled case for ``c_notice_id`` and return the file path.

    Raises ``SectionNotStored`` when there is no Section 3 on file and no
    client was given. That is a better answer than an empty case file, which
    would look like a notice whose buyer asks for nothing.
    """
    notice = _stored_notice(store, c_notice_id)

    if client is not None:
        # The portal's Section 3 is keyed by the *init* notice id, which is a
        # different number from the cNoticeId in the search results. Which of
        # the two the endpoint really wants is still unconfirmed against the
        # live portal (see STATUS.md, immediate step 1), so prefer the stored
        # init id when there is one and fall back to the id we were handed.
        init_id = (notice.init_notice_id if notice else None) or c_notice_id
        raw = client.get_section3(init_id)
        store.save_section3(c_notice_id, raw)

    section3 = store.section3(c_notice_id)
    if section3 is None:
        raise SectionNotStored(
            f"no Section 3 stored for {c_notice_id}. Fetch it first on a machine that "
            "can reach the portal, or pass a client to capture it now."
        )

    return write_case(
        directory=directory,
        name=_case_name(c_notice_id, notice.notice_no if notice else None),
        section3_raw=section3.raw,
        c_notice_id=c_notice_id,
        notice_no=notice.notice_no if notice else None,
    )


def _stored_notice(store: Store, c_notice_id: str) -> Any | None:
    """Find the stored notice, so the case file can carry its notice number."""
    for notice in store.notices():
        if notice.c_notice_id == c_notice_id:
            return notice
    return None


def _case_name(c_notice_id: str, notice_no: str | None) -> str:
    """Name the file after the notice number a human recognises."""
    stem = (notice_no or f"id{c_notice_id}").strip()
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in stem).lower()
