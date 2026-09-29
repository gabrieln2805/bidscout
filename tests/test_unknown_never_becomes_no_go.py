"""Ground rule 2 of this project, held in place by tests.

"We could not tell" must never be printed as "you do not qualify". Only a
gate where both numbers are known may produce NO-GO.
"""

from bidscout.decide.engine import decide
from bidscout.extract.gates import extract_requirements
from bidscout.models import Decision


def test_a_company_that_clears_every_gate_gets_go(section3_full, strong_profile, rules) -> None:
    verdict = decide(
        extract_requirements(section3_full),
        strong_profile,
        rules,
        {"cpv": "72000000", "estimated_value_ron": 1804000, "days_to_deadline": 30},
    )
    assert verdict.decision is Decision.GO


def test_a_measured_shortfall_is_the_only_road_to_no_go(
    section3_full, small_profile, rules
) -> None:
    verdict = decide(extract_requirements(section3_full), small_profile, rules)
    assert verdict.decision is Decision.NO_GO
    assert any("annual turnover" in reason.text for reason in verdict.reasons)


def test_an_unreadable_requirement_gives_check_not_no_go(
    section3_vague, small_profile, rules
) -> None:
    verdict = decide(extract_requirements(section3_vague), small_profile, rules)
    assert verdict.decision is Decision.CHECK
    assert "annual turnover" in verdict.unresolved


def test_a_missing_profile_figure_gives_check_not_no_go(section3_full, rules) -> None:
    """An empty profile means we know nothing about the company, not that it fails."""
    verdict = decide(extract_requirements(section3_full), {"company_name": "Blank SRL"}, rules)
    assert verdict.decision is Decision.CHECK
    assert len(verdict.unresolved) == 3


def test_every_gate_reason_carries_the_buyers_own_words(
    section3_full, strong_profile, rules
) -> None:
    verdict = decide(extract_requirements(section3_full), strong_profile, rules)
    quoted = [reason for reason in verdict.reasons if reason.quote]
    assert len(quoted) >= 3
    assert any("2.700.000,00" in (reason.quote or "") for reason in quoted)


def test_a_gate_the_buyer_never_asks_for_is_not_held_against_anyone(
    section3_vague, strong_profile, rules
) -> None:
    verdict = decide(extract_requirements(section3_vague), strong_profile, rules)
    assert any("does not ask for one" in reason.text for reason in verdict.reasons)
    assert verdict.decision is not Decision.NO_GO


def test_score_stays_inside_zero_and_one_hundred(section3_full, strong_profile, rules) -> None:
    verdict = decide(
        extract_requirements(section3_full),
        strong_profile,
        rules,
        {"cpv": "72000000", "estimated_value_ron": 1804000, "days_to_deadline": 90},
    )
    assert 0 <= verdict.score <= 100
