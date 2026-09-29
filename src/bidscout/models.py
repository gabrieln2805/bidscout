"""The few shapes that travel between the parts of bidscout.

Two fields here exist because of ground rule 3 (keep the raw data for ever):
``Notice.raw`` and ``Section3.raw``. The reader has been rewritten several
times, and each rewrite was replayed against stored copies instead of polling
the portal again. Never drop them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Confidence(StrEnum):
    """How much a fact can be trusted to decide anything.

    ``LOW`` exists to serve ground rule 2: a requirement we could read but not
    measure must produce CHECK, never NO-GO.
    """

    HIGH = "high"
    LOW = "low"


class Decision(StrEnum):
    """The only three answers bidscout ever gives."""

    GO = "GO"
    CHECK = "CHECK"
    NO_GO = "NO-GO"


@dataclass(frozen=True)
class Requirement:
    """One qualification requirement, with the sentence it was read from.

    ``quote`` is mandatory. A fact with no quote cannot be checked by the
    user, so the extractor drops it rather than carry it forward.
    """

    kind: str
    amount: Decimal | None
    currency: str | None
    quote: str
    source_field: str
    confidence: Confidence

    def __post_init__(self) -> None:
        if not self.quote.strip():
            raise ValueError(f"requirement {self.kind!r} has no quote; it must be dropped")


@dataclass
class Section3:
    """The qualification section of a notice, as the portal returned it."""

    init_notice_id: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    def text(self, key: str) -> str:
        """Return one Section 3 field as plain text, or an empty string."""
        from bidscout.extract.html import strip_html  # noqa: PLC0415 - avoids a cycle

        return strip_html(self.raw.get(key) or "")


@dataclass
class Notice:
    """One tender as it appears in the search results."""

    c_notice_id: str
    notice_no: str
    init_notice_id: str | None
    title: str
    buyer: str
    cpv: str | None
    estimated_value_ron: Decimal | None
    published_at: str | None
    deadline_at: str | None
    notice_type_id: int | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def is_simplified(self) -> bool:
        """True for an SCN notice, which has no working detail view yet."""
        return self.notice_no.upper().startswith("SCN") or self.notice_type_id == 17


@dataclass(frozen=True)
class Reason:
    """One line of the explanation behind a verdict."""

    text: str
    quote: str | None = None
    source_field: str | None = None


@dataclass
class Verdict:
    """The answer for one notice and one company."""

    decision: Decision
    score: int
    reasons: list[Reason] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
