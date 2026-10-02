"""The one thing ``fetch`` must never make possible: a GO nobody read.

``score_stored`` skips a notice with no stored Section 3, because with nothing
on file every gate reads "the buyer does not ask for one", nothing is
unresolved, and the score alone decides — so an unread notice would come out
GO. ``fetch`` is the command that writes those sections, which makes it the
one thing that could put a payload in the database that the reader cannot
understand.

The guard is in ``decide``, not in ``fetch``: a section we recognised nothing
in is CHECK. That is deliberate. Any command that stores a section is then
safe, the raw payload is still kept (ground rule 3), and a parser fix applies
to it on the next score instead of the notice having been thrown away.
"""

from __future__ import annotations

from datetime import UTC, datetime

from bidscout.decide.engine import decide
from bidscout.models import Decision
from bidscout.pipeline import notice_from_item, score_stored
from bidscout.store.db import Store

TODAY = datetime(2026, 9, 20, tzinfo=UTC)

#: A section whose only prose sits in a field the reader does not look at.
#: ``efCriteriaBold1`` is, by its name, where a bold financial criterion goes,
#: so this is a plausible payload and not a contrived one.
ONLY_UNREAD_FIELDS = {
    "efCriteriaBold1": "<p><b>Cifra de afaceri medie anuala: 2.700.000,00 Lei</b></p>",
    "prCriteria": "<p>Criterii de atribuire: pretul cel mai scazut</p>",
}


def _scored(store: Store, profile, rules):
    return score_stored(store, profile, rules, today=TODAY).verdicts[0][1]


def test_an_empty_section_is_held_at_check(tmp_path, notice_item, strong_profile, rules) -> None:
    """The headline case: `{}` on file is "we could not tell", not "go and bid"."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", {})
        verdict = _scored(store, strong_profile, rules)
    assert verdict.decision is Decision.CHECK
    assert any("recognised none" in reason.text for reason in verdict.reasons)


def test_a_section_whose_text_the_reader_cannot_see_is_held_at_check(
    tmp_path, notice_item, strong_profile, rules
) -> None:
    """The subtler case, and the one that defeats a guard written as a field list.

    A payload can carry the buyer's own words — a 2.7 million turnover rule, in
    bold — in a field no gate maps to. Any check that asked only "is there text
    in this payload" would pass it as a real section, store it, and then score
    it with every gate absent. Measuring the verdict instead of the payload is
    what makes the field list irrelevant.
    """
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", ONLY_UNREAD_FIELDS)
        verdict = _scored(store, strong_profile, rules)
    assert verdict.decision is Decision.CHECK


def test_the_reason_sends_the_reader_to_the_section_itself(
    tmp_path, notice_item, strong_profile, rules
) -> None:
    """CHECK is only useful if it says what to go and look at."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", {})
        verdict = _scored(store, strong_profile, rules)
    assert "every requirement (nothing in Section 3 was recognised)" in verdict.unresolved
    assert any("read the section yourself" in reason.text for reason in verdict.reasons)


def test_a_section_the_reader_does_understand_is_unaffected(
    tmp_path, notice_item, section3_full, strong_profile, rules
) -> None:
    """The guard must not turn every verdict into CHECK."""
    with Store(tmp_path / "t.sqlite3") as store:
        store.save_notice(notice_from_item(notice_item))
        store.save_section3("1096282", section3_full.raw)
        assert _scored(store, strong_profile, rules).decision is Decision.GO


def test_one_recognised_requirement_is_enough_to_leave_the_guard_alone(
    section3_vague, strong_profile, rules
) -> None:
    """The guard fires on *nothing* recognised, not on a gate the buyer omits.

    ``section3_vague`` states a turnover rule with no figure. That is one
    requirement read, so the ordinary unreadable-requirement path applies and
    this new reason must not appear on top of it.
    """
    from bidscout.extract.gates import extract_requirements

    verdict = decide(extract_requirements(section3_vague), strong_profile, rules)
    assert not any("recognised none" in reason.text for reason in verdict.reasons)


def test_a_rule_set_with_no_gates_is_not_held_at_check(strong_profile, rules) -> None:
    """Nothing to measure is not the same as something we failed to measure."""
    from bidscout.decide.rules import RuleSet

    gateless = RuleSet(name="no gates", gates=[], weights=rules.weights)
    verdict = decide([], strong_profile, gateless, {"cpv": "72000000"})
    assert not any("recognised none" in reason.text for reason in verdict.reasons)
