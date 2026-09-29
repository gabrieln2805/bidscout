"""Read the qualification gates out of Section 3.

Each Section 3 field maps to one kind of requirement. The mapping is data,
not code, so adding a field is one line. Every requirement keeps the sentence
it came from; a field with text but no readable amount becomes a
low-confidence requirement, which the decision engine turns into CHECK.
"""

from __future__ import annotations

from bidscout.extract.money import parse_amount
from bidscout.models import Confidence, Requirement, Section3

#: Section 3 field -> requirement kind. The ``Min`` fields hold the measurable
#: threshold; the plain field holds the buyer's full prose and is the fallback.
FIELD_MAP: dict[str, tuple[str, ...]] = {
    "turnover": ("efCriteriaMin", "efCriteria"),
    "experience": ("tpCriteriaQAStandardMin", "tpCriteriaQAStandard"),
    "deposit": ("depositsAndWarranties",),
    "qualification": ("mandatoryProfesionalQualif",),
    "personal_situation": ("personalSituation",),
}

#: Kinds where a number is the whole point. A kind outside this set is read
#: for its text only, so a missing amount is normal and not a warning sign.
NUMERIC_KINDS = frozenset({"turnover", "experience", "deposit"})


def extract_requirements(section3: Section3) -> list[Requirement]:
    """Return every requirement bidscout can read from ``section3``.

    A field that is empty produces nothing at all: an absent requirement is
    not the same as a requirement of zero, and treating it as zero would let a
    notice pass a gate it was never measured against.
    """
    found: list[Requirement] = []
    for kind, fields in FIELD_MAP.items():
        requirement = _first_readable(section3, kind, fields)
        if requirement is not None:
            found.append(requirement)
    return found


def _first_readable(section3: Section3, kind: str, fields: tuple[str, ...]) -> Requirement | None:
    """Take the first field that has text, preferring the measurable one."""
    fallback: Requirement | None = None
    for name in fields:
        text = section3.text(name)
        if not text:
            continue
        money = parse_amount(text) if kind in NUMERIC_KINDS else None
        amount, currency = money if money else (None, None)
        confidence = (
            Confidence.HIGH
            if (kind not in NUMERIC_KINDS or amount is not None)
            else Confidence.LOW
        )
        requirement = Requirement(
            kind=kind,
            amount=amount,
            currency=currency,
            quote=_shorten(text),
            source_field=name,
            confidence=confidence,
        )
        if confidence is Confidence.HIGH:
            return requirement
        fallback = fallback or requirement
    return fallback


def _shorten(text: str, limit: int = 600) -> str:
    """Keep a quote readable without losing the part that carries the number."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rsplit(" ", 1)[0] + "…"
