"""Turn requirements plus a company profile into GO, CHECK or NO-GO.

Ground rule 2 of this project is enforced here and nowhere else: a fact we
could not read, or a profile figure the user never filled in, produces CHECK.
It never produces NO-GO. The user is told what is missing instead of being
told they do not qualify.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bidscout.decide.rules import RuleSet
from bidscout.models import Confidence, Decision, Reason, Requirement, Verdict


def decide(
    requirements: list[Requirement],
    profile: dict[str, Any],
    rules: RuleSet,
    context: dict[str, Any] | None = None,
) -> Verdict:
    """Apply ``rules`` to ``requirements`` for the company in ``profile``."""
    context = context or {}
    by_kind = {req.kind: req for req in requirements}
    reasons: list[Reason] = []
    unresolved: list[str] = []
    failed = False

    for gate in rules.gates:
        requirement = by_kind.get(gate.kind)
        if requirement is None:
            reasons.append(Reason(f"{gate.label}: the buyer does not ask for one."))
            continue
        outcome, reason = _check_gate(gate, requirement, profile)
        reasons.append(reason)
        if outcome is _FAIL:
            failed = True
        elif outcome is _UNKNOWN:
            unresolved.append(gate.label)

    score = _score(requirements, profile, rules, context, reasons)

    if failed:
        # A gate that the buyer states and the company misses is the one case
        # where NO-GO is honest: both numbers are known and they do not meet.
        return Verdict(Decision.NO_GO, score, reasons, unresolved)
    if unresolved:
        return Verdict(Decision.CHECK, score, reasons, unresolved)
    if score >= rules.go_threshold:
        return Verdict(Decision.GO, score, reasons, unresolved)
    return Verdict(Decision.CHECK, score, reasons, unresolved)


_PASS, _FAIL, _UNKNOWN = "pass", "fail", "unknown"


def _check_gate(gate: Any, requirement: Requirement, profile: dict[str, Any]) -> tuple[str, Reason]:
    """Compare one requirement against the profile, keeping the buyer's quote."""
    if requirement.confidence is Confidence.LOW or requirement.amount is None:
        return _UNKNOWN, Reason(
            f"{gate.label}: the buyer states a requirement but no figure could be read. "
            "Read the quote and decide by hand.",
            quote=requirement.quote,
            source_field=requirement.source_field,
        )

    have = profile.get(gate.profile_key)
    if have is None:
        return _UNKNOWN, Reason(
            f"{gate.label}: the buyer asks for {_money(requirement.amount)}, "
            f"but {gate.profile_key} is not filled in your profile.",
            quote=requirement.quote,
            source_field=requirement.source_field,
        )

    have = Decimal(str(have))
    if have >= requirement.amount:
        return _PASS, Reason(
            f"{gate.label}: the buyer asks for {_money(requirement.amount)}; "
            f"you have {_money(have)}.",
            quote=requirement.quote,
            source_field=requirement.source_field,
        )
    return _FAIL, Reason(
        f"{gate.label}: the buyer asks for {_money(requirement.amount)}; "
        f"you have {_money(have)}.",
        quote=requirement.quote,
        source_field=requirement.source_field,
    )


def _score(
    requirements: list[Requirement],
    profile: dict[str, Any],
    rules: RuleSet,
    context: dict[str, Any],
    reasons: list[Reason],
) -> int:
    """A 0-100 number for everything that is not a hard gate.

    The score never decides GO on its own; it orders the list so that the
    strongest opportunities are read first.
    """
    earned = 0
    for key, weight in rules.weights.items():
        fraction = _component(key, requirements, profile, context)
        if fraction is None:
            continue
        earned += int(round(weight * fraction))
    return max(0, min(100, int(round(100 * earned / rules.total_weight))))


def _component(
    key: str,
    requirements: list[Requirement],
    profile: dict[str, Any],
    context: dict[str, Any],
) -> float | None:
    """Return 0.0-1.0 for one scoring component, or None when not measurable."""
    if key == "cpv_match":
        watchlist = {str(code) for code in profile.get("cpv_watchlist", [])}
        cpv = str(context.get("cpv") or "")
        if not watchlist or not cpv:
            return None
        return 1.0 if any(cpv.startswith(code[:4]) for code in watchlist) else 0.0

    if key == "value_fit":
        value = context.get("estimated_value_ron")
        low = profile.get("min_contract_ron")
        high = profile.get("max_contract_ron")
        if value is None or low is None or high is None:
            return None
        value, low, high = Decimal(str(value)), Decimal(str(low)), Decimal(str(high))
        return 1.0 if low <= value <= high else 0.0

    if key == "headroom":
        return _headroom(requirements, profile)

    if key == "deadline":
        days = context.get("days_to_deadline")
        if days is None:
            return None
        # Under a week is very hard to answer well; over three weeks is comfortable.
        return max(0.0, min(1.0, (float(days) - 5.0) / 16.0))

    return None


def _headroom(requirements: list[Requirement], profile: dict[str, Any]) -> float | None:
    """How comfortably the company clears the gates it does meet.

    Clearing a gate exactly scores nothing; clearing it twice over scores
    full marks. A company that only just qualifies usually loses on price.
    """
    ratios: list[float] = []
    for requirement in requirements:
        key = {"turnover": "average_turnover_ron", "experience": "similar_experience_ron"}.get(
            requirement.kind
        )
        have = profile.get(key) if key else None
        if have is None or requirement.amount is None or requirement.amount == 0:
            continue
        ratios.append(float(Decimal(str(have)) / requirement.amount))
    if not ratios:
        return None
    return max(0.0, min(1.0, (min(ratios) - 1.0)))


def _money(value: Decimal) -> str:
    """Format a sum the way a Romanian reader expects to see it."""
    whole = f"{value:,.0f}".replace(",", ".")
    return f"{whole} RON"
