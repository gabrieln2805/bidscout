"""A threshold the buyer wrote in euro must not be compared against lei.

Found on 1 October 2026 by putting the demo through the web page: the engine
read "Garanția de participare este de 4.500,00 euro" correctly as 4500 EUR, then
compared the bare number against a profile figure in lei and printed "the buyer
asks for 4.500 RON". Two faults in one line — a false claim about the buyer's
own sentence, and a comparison roughly five times too lenient, which can let a
tender pass a gate it was never measured against.

The honest answer is CHECK: the rate that applies is the one on the notice's own
date, which bidscout cannot look up and cannot verify.
"""

from decimal import Decimal

import pytest

from bidscout.decide.engine import PROFILE_CURRENCY, decide
from bidscout.decide.rules import Gate, RuleSet
from bidscout.models import Confidence, Decision, Requirement

GUARANTEE = Gate(kind="deposit", profile_key="available_guarantee_ron", label="guarantee")
RULES = RuleSet(name="test", gates=[GUARANTEE], weights={"headroom": 1})
PROFILE = {"company_name": "Example SRL", "available_guarantee_ron": Decimal(50000)}


def _deposit(amount: str, currency: str) -> Requirement:
    return Requirement(
        kind="deposit",
        amount=Decimal(amount),
        currency=currency,
        quote=f"Garantia de participare este de {amount} {currency}.",
        source_field="depositsAndWarranties",
        confidence=Confidence.HIGH,
    )


def test_a_euro_guarantee_is_check_even_when_the_bare_number_would_pass() -> None:
    """4.500 EUR is about 22.000 RON. The company holds 50.000 RON and may well
    clear it — but "may well" is not "does", so the verdict is CHECK."""
    verdict = decide([_deposit("4500", "EUR")], PROFILE, RULES)
    assert verdict.decision is Decision.CHECK
    assert "guarantee" in verdict.unresolved


def test_the_reason_names_the_currency_the_buyer_actually_wrote() -> None:
    """The old text said "4.500 RON" for a sentence that says euro."""
    verdict = decide([_deposit("4500", "EUR")], PROFILE, RULES)
    text = " ".join(reason.text for reason in verdict.reasons)
    assert "4.500 EUR" in text
    assert "4.500 RON" not in text


def test_a_euro_threshold_can_never_be_a_no_go() -> None:
    """A figure we cannot convert must not be read as a measured shortfall."""
    poor = {"company_name": "Small SRL", "available_guarantee_ron": Decimal(10)}
    assert decide([_deposit("4500", "EUR")], poor, RULES).decision is not Decision.NO_GO


def test_a_lei_threshold_is_still_compared_normally() -> None:
    """The guard must not defer every gate. A lei figure is still measured.

    The decision is read off the gate, not off the verdict: this rule set
    weights headroom only, which no deposit gate contributes to, so a passing
    deposit still leaves the score below the GO threshold.
    """
    measured = decide([_deposit("27000", "RON")], PROFILE, RULES)
    assert measured.unresolved == []
    assert "you have 50.000 RON" in " ".join(r.text for r in measured.reasons)

    poor = {"company_name": "Small SRL", "available_guarantee_ron": Decimal(10)}
    assert decide([_deposit("27000", "RON")], poor, RULES).decision is Decision.NO_GO


def test_headroom_does_not_divide_lei_by_euro() -> None:
    """A euro requirement must not inflate the score through the headroom term.

    Dividing 900.000 lei by 450.000 euro would read as two times' headroom on a
    gate that is really about four times tighter.
    """
    profile = {"company_name": "X", "similar_experience_ron": Decimal(900000)}
    rules = RuleSet(
        name="t",
        gates=[Gate(kind="experience", profile_key="similar_experience_ron", label="experience")],
        weights={"headroom": 100},
    )
    euro = Requirement(
        kind="experience",
        amount=Decimal(450000),
        currency="EUR",
        quote="servicii similare in valoare cumulata de minimum 450.000,00 euro",
        source_field="tpCriteriaQAStandardMin",
        confidence=Confidence.HIGH,
    )
    lei = Requirement(**{**euro.__dict__, "currency": "RON"})
    assert decide([euro], profile, rules).score < decide([lei], profile, rules).score


@pytest.mark.parametrize("currency", ["RON", None])
def test_the_profile_currency_is_what_passes_through(currency: str | None) -> None:
    """Both an explicit RON and an unmarked figure are treated as lei.

    ``parse_amount`` already defaults an unmarked grouped number to RON, because
    Romanian tenders are written in lei. This records that assumption where the
    comparison happens.
    """
    requirement = Requirement(
        kind="deposit",
        amount=Decimal(27000),
        currency=currency,
        quote="Garantia de participare este de 27.000,00.",
        source_field="depositsAndWarranties",
        confidence=Confidence.HIGH,
    )
    assert PROFILE_CURRENCY == "RON"
    verdict = decide([requirement], PROFILE, RULES)
    assert verdict.unresolved == []
    assert verdict.decision is not Decision.NO_GO
