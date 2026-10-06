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
            reasons.append(
                Reason(f"{gate.label}: the buyer does not ask for one.", outcome=_ABSENT)
            )
            continue
        outcome, reason = _check_gate(gate, requirement, profile)
        reasons.append(reason)
        if outcome is _FAIL:
            failed = True
        elif outcome is _UNKNOWN:
            unresolved.append(gate.label)

    # Nothing recognised at all is not a buyer who asks for nothing.
    #
    # A public tender states qualification criteria; a Section 3 from which the
    # reader took not one requirement means the section was there and we did not
    # understand it. Left alone, every gate reads "the buyer does not ask for
    # one", nothing is unresolved, and the score alone decides — so an
    # unreadable section comes out GO. That is ground rule 2 upside down, and
    # it is the shape of failure that an empty or unparsed payload in the
    # ``sections`` table would otherwise produce. The guard lives here rather
    # than in whichever command fetched the section, because this is the one
    # place that turns "we could not tell" into CHECK.
    if rules.gates and not requirements:
        reasons.append(
            Reason(
                "bidscout read this notice's Section 3 and recognised none of the "
                "qualification criteria in it. That is not the same as a buyer who "
                "asks for nothing: read the section yourself before deciding.",
                outcome=_UNKNOWN,
            )
        )
        unresolved.append("every requirement (nothing in Section 3 was recognised)")

    # A tender split into lots states requirements we have not matched to a
    # lot. The notice-level figure may be the total for every lot together,
    # while you would bid for one. Comparing your company against the total and
    # printing NO-GO would be exactly the "we could not tell" that ground rule 2
    # forbids, so an unread lot structure holds the verdict at CHECK.
    lots_unread = bool(context.get("has_lots"))
    if lots_unread:
        reasons.append(
            Reason(
                "This tender is split into lots, and bidscout has not read them yet. "
                "The figures above may be the total for all lots, not the lot you "
                "would bid for. Open the lot list before deciding.",
                outcome=_UNKNOWN,
            )
        )
        unresolved.append("the lots (not read yet)")

    # A tender outside the company's line of work is never a GO, however well
    # the company clears its figures. The score has a CPV component, but the
    # others (value, headroom, deadline) can pass the threshold without it: on
    # the first live run a security-guard tender scored GO 75 for an IT company.
    # It is held at CHECK, not NO-GO: bidding outside your CPV codes is allowed,
    # and whether you want to is the company's call, not a fact we measured.
    if _in_watchlist(profile, context.get("cpv")) is False:
        cpv = str(context.get("cpv"))
        reasons.append(
            Reason(
                f"Sector: CPV {cpv} is outside your watchlist "
                f"({', '.join(str(code) for code in profile.get('cpv_watchlist', []))}). "
                "The figures may fit, but this is not your line of work as your profile "
                "describes it. Decide whether you want it before reading further.",
                source_field="cpvCodeAndName",
                outcome=_FAIL,
            )
        )
        unresolved.append(f"the sector (CPV {cpv} is not in your watchlist)")

    score = _score(requirements, profile, rules, context, reasons)

    if failed and not lots_unread:
        # A gate that the buyer states and the company misses is the one case
        # where NO-GO is honest: both numbers are known and they do not meet.
        return Verdict(Decision.NO_GO, score, reasons, unresolved)
    if unresolved:
        return Verdict(Decision.CHECK, score, reasons, unresolved)
    if score >= rules.go_threshold:
        return Verdict(Decision.GO, score, reasons, unresolved)
    return Verdict(Decision.CHECK, score, reasons, unresolved)


#: What a gate did. ``ABSENT`` is not a failure: a requirement the buyer never
#: states cannot be held against anybody.
_PASS, _FAIL, _UNKNOWN, _ABSENT = "pass", "fail", "unknown", "absent"

#: The currency every figure in ``profile.yaml`` is written in. A requirement in
#: any other currency is not comparable without a rate bidscout cannot verify.
PROFILE_CURRENCY = "RON"


def _check_gate(gate: Any, requirement: Requirement, profile: dict[str, Any]) -> tuple[str, Reason]:
    """Compare one requirement against the profile, keeping the buyer's quote."""
    if requirement.confidence is Confidence.LOW or requirement.amount is None:
        return _UNKNOWN, Reason(
            f"{gate.label}: the buyer states a requirement but no figure could be read. "
            "Read the quote and decide by hand.",
            quote=requirement.quote,
            source_field=requirement.source_field,
            outcome=_UNKNOWN,
        )

    # The profile is in lei. A threshold the buyer wrote in another currency
    # cannot be compared without an exchange rate, and the rate that applies is
    # the one on the notice's own date — a live fact bidscout cannot check. So
    # this is a "we could not tell", which ground rule 2 turns into CHECK.
    # Comparing the bare number would understate a euro guarantee about fivefold
    # and quietly let a tender pass a gate it was never measured against.
    if requirement.currency and requirement.currency != PROFILE_CURRENCY:
        return _UNKNOWN, Reason(
            f"{gate.label}: the buyer asks for "
            f"{_money(requirement.amount, requirement.currency)}, and your profile is in "
            f"{PROFILE_CURRENCY}. bidscout does not convert currencies, so convert this "
            "one by hand before deciding.",
            quote=requirement.quote,
            source_field=requirement.source_field,
            outcome=_UNKNOWN,
        )

    have = profile.get(gate.profile_key)
    if have is None:
        return _UNKNOWN, Reason(
            f"{gate.label}: the buyer asks for {_money(requirement.amount)}, "
            f"but {gate.profile_key} is not filled in your profile.",
            quote=requirement.quote,
            source_field=requirement.source_field,
            outcome=_UNKNOWN,
        )

    have = Decimal(str(have))
    if have >= requirement.amount:
        return _PASS, Reason(
            f"{gate.label}: the buyer asks for {_money(requirement.amount)}; "
            f"you have {_money(have)}.",
            quote=requirement.quote,
            source_field=requirement.source_field,
            outcome=_PASS,
        )
    return _FAIL, Reason(
        f"{gate.label}: the buyer asks for {_money(requirement.amount)}; "
        f"you have {_money(have)}.",
        quote=requirement.quote,
        source_field=requirement.source_field,
        outcome=_FAIL,
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
        match = _in_watchlist(profile, context.get("cpv"))
        if match is None:
            return None
        return 1.0 if match else 0.0

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


def _in_watchlist(profile: dict[str, Any], cpv: Any) -> bool | None:
    """Whether the notice's primary CPV is in the profile's watchlist.

    None when either side is missing: no watchlist, or a notice with no CPV,
    is "we could not tell", never "outside your line of work".

    CPV codes are a tree, and the trailing zeros say which level a code names:
    72000000 is all of division 72, 72260000 one group inside it. So a
    watchlist entry matches every code that starts with its significant
    digits. Comparing a fixed four digits, as this did until 6 October 2026,
    put software services (72260000) outside an IT-services (72000000)
    watchlist.
    """
    prefixes = [_significant(code) for code in profile.get("cpv_watchlist") or []]
    prefixes = [prefix for prefix in prefixes if prefix]
    code = str(cpv or "").split("-")[0].strip()
    if not prefixes or not code:
        return None
    return any(code.startswith(prefix) for prefix in prefixes)


def _significant(code: Any) -> str:
    """"72000000-5" -> "72", "30200000" -> "302": the digits that name the node.

    Never shorter than the two-digit division, so a stray "00000000" cannot
    match everything.
    """
    digits = str(code).split("-")[0].strip()
    trimmed = digits.rstrip("0")
    return digits[:2] if len(trimmed) < 2 else trimmed


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
        if requirement.currency and requirement.currency != PROFILE_CURRENCY:
            # Dividing lei by euro would invent headroom out of an exchange
            # rate nobody applied. The gate already reports this as CHECK.
            continue
        ratios.append(float(Decimal(str(have)) / requirement.amount))
    if not ratios:
        return None
    return max(0.0, min(1.0, (min(ratios) - 1.0)))


def _money(value: Decimal, currency: str = PROFILE_CURRENCY) -> str:
    """Format a sum the way a Romanian reader expects to see it.

    The currency is a parameter, not a constant, because a buyer may state a
    guarantee in euro. Printing "4.500 RON" for "4.500,00 euro" would be a
    false claim about the buyer's own sentence.
    """
    whole = f"{value:,.0f}".replace(",", ".")
    return f"{whole} {currency}"
