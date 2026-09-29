"""Read a money amount out of a Romanian tender sentence.

Romanian tenders write "2.700.000,00 Lei": dot for thousands, comma for
decimals — the opposite of the Python default. Reading that with a plain
``float()`` gives 2.7, which is a thousand times too small and would turn a
GO into a NO-GO. That is the single most dangerous parse in this codebase,
so it lives in its own module with its own tests.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

#: A number with Romanian grouping, followed by an optional currency word.
_AMOUNT = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*"
    r"(lei|ron|eur|euro)?",
    re.IGNORECASE,
)

_CURRENCY = {"lei": "RON", "ron": "RON", "eur": "EUR", "euro": "EUR"}

#: Below this, a "number" in a tender sentence is almost always a count of
#: contracts or a number of months, not a sum of money.
MIN_PLAUSIBLE_AMOUNT = Decimal(1000)


def parse_amount(text: str) -> tuple[Decimal, str] | None:
    """Return the largest plausible money amount in ``text``, with its currency.

    The largest is taken, not the first, because the sentence usually names the
    period and the number of contracts before it names the sum:
    "in ultimii 3 ani, in cadrul a maxim 2 contracte, ... cel putin 1.804.000,00 lei".
    Returns ``None`` when nothing in the sentence looks like money, which the
    caller must turn into a low-confidence requirement rather than a zero.
    """
    best: tuple[Decimal, str] | None = None
    for match in _AMOUNT.finditer(text):
        raw, unit = match.group(1), match.group(2)
        if not _looks_like_money(raw, unit):
            continue
        value = _to_decimal(raw)
        if value is None or value < MIN_PLAUSIBLE_AMOUNT:
            continue
        currency = _CURRENCY.get((unit or "").lower(), "RON")
        if best is None or value > best[0]:
            best = (value, currency)
    return best


def _looks_like_money(raw: str, unit: str | None) -> bool:
    """Reject a bare number that carries no sign of being a sum.

    "ultimele 3 exercitii financiare (2023, 2024, 2025)" holds three numbers
    above the plausibility floor, and every one of them is a year. A figure is
    only treated as money when the buyer wrote it like money: with thousand
    groups, with decimals, or with the currency named next to it.
    """
    has_group = "." in raw or " " in raw
    has_decimals = "," in raw
    return bool(unit) or has_group or has_decimals


def _to_decimal(raw: str) -> Decimal | None:
    """Convert "2.700.000,00" to ``Decimal("2700000.00")``.

    A group separator is only removed when it really separates groups of three
    digits. This is what keeps "1.804" (one thousand eight hundred and four)
    apart from a decimal point that a buyer typed in the English style.
    """
    cleaned = raw.replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
