"""Every extracted requirement carries the sentence it was read from."""

from decimal import Decimal

import pytest

from bidscout.extract.gates import extract_requirements
from bidscout.models import Confidence, Requirement


def test_turnover_and_experience_are_read_from_section3(section3_full) -> None:
    by_kind = {r.kind: r for r in extract_requirements(section3_full)}
    assert by_kind["turnover"].amount == Decimal("2700000.00")
    assert by_kind["experience"].amount == Decimal("1804000.00")
    assert by_kind["deposit"].amount == Decimal("27000.00")


def test_every_requirement_has_a_quote_and_a_source_field(section3_full) -> None:
    for requirement in extract_requirements(section3_full):
        assert requirement.quote.strip()
        assert requirement.source_field


def test_a_requirement_with_no_quote_cannot_be_built() -> None:
    """A fact the user cannot check must be dropped, not carried forward."""
    with pytest.raises(ValueError, match="no quote"):
        Requirement(
            kind="turnover",
            amount=Decimal(1),
            currency="RON",
            quote="   ",
            source_field="efCriteriaMin",
            confidence=Confidence.HIGH,
        )


def test_a_stated_but_unmeasurable_rule_is_low_confidence(section3_vague) -> None:
    """"corespunzatoare valorii estimate" is a real rule with no number in it."""
    by_kind = {r.kind: r for r in extract_requirements(section3_vague)}
    assert by_kind["turnover"].confidence is Confidence.LOW
    assert by_kind["turnover"].amount is None


def test_an_empty_field_produces_nothing_at_all(section3_vague) -> None:
    """Absent is not the same as zero. Zero would pass the gate silently."""
    kinds = {r.kind for r in extract_requirements(section3_vague)}
    assert "experience" not in kinds
    assert "deposit" not in kinds
