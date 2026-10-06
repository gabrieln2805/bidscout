"""A tender outside the company's line of work is never a GO.

Found on the first live run, 2 October 2026: a security-guard tender (CPV
79713000) scored GO 75 for an IT company, and it was the first GO on the public
page. The score's CPV component is only 25 of 100; value fit, headroom and the
deadline can carry a notice past the threshold without it.

It is held at CHECK, not NO-GO. Bidding outside your CPV codes is allowed;
whether you want to is the company's decision, not a figure we measured.
"""

from bidscout.decide.engine import decide
from bidscout.extract.gates import extract_requirements
from bidscout.models import Decision

IT = {"cpv": "72000000", "estimated_value_ron": 1804000, "days_to_deadline": 30}
GUARDS = {**IT, "cpv": "79713000"}


def test_the_same_notice_is_go_in_sector_and_check_outside_it(
    section3_full, strong_profile, rules
) -> None:
    """Both halves: a change that made every verdict CHECK would fail the first."""
    requirements = extract_requirements(section3_full)
    assert decide(requirements, strong_profile, rules, IT).decision is Decision.GO

    outside = decide(requirements, strong_profile, rules, GUARDS)
    assert outside.decision is Decision.CHECK
    assert any("79713000" in item for item in outside.unresolved)


def test_the_reason_names_the_sector_and_is_marked_on_the_page(
    section3_full, strong_profile, rules
) -> None:
    """The page marks lines from ``outcome``; this one must not read as a pass."""
    verdict = decide(extract_requirements(section3_full), strong_profile, rules, GUARDS)
    sector = [reason for reason in verdict.reasons if reason.text.startswith("Sector:")]
    assert len(sector) == 1
    assert sector[0].outcome == "fail"
    assert "72000000" in sector[0].text


def test_a_real_no_go_outside_the_sector_stays_no_go(
    section3_full, small_profile, rules
) -> None:
    """The sector rule only stops a GO; it never softens a gate both numbers decide."""
    verdict = decide(extract_requirements(section3_full), small_profile, rules, GUARDS)
    assert verdict.decision is Decision.NO_GO


def test_no_watchlist_or_no_cpv_is_not_out_of_sector(
    section3_full, strong_profile, rules
) -> None:
    """Missing on either side is "we could not tell", not "not your line of work"."""
    requirements = extract_requirements(section3_full)
    no_list = {key: value for key, value in strong_profile.items() if key != "cpv_watchlist"}
    for profile, context in ((no_list, GUARDS), (strong_profile, {**IT, "cpv": None})):
        verdict = decide(requirements, profile, rules, context)
        assert not any(reason.text.startswith("Sector:") for reason in verdict.reasons)


def test_the_first_four_digits_decide_as_the_profile_says(
    section3_full, strong_profile, rules
) -> None:
    """72260000 (software services) is inside a 72000000 watchlist entry."""
    verdict = decide(
        extract_requirements(section3_full), strong_profile, rules, {**IT, "cpv": "72260000"}
    )
    assert verdict.decision is Decision.GO
