"""Romanian tenders write 2.700.000,00 — dot for thousands, comma for decimals.

Reading that with float() gives 2.7, which is a thousand times too small and
would turn a GO into a NO-GO. This is the most dangerous parse in the code.
"""

from decimal import Decimal

from bidscout.extract.money import parse_amount


def test_thousand_separators_are_not_decimal_points() -> None:
    assert parse_amount("egala cu 2.700.000,00 Lei") == (Decimal("2700000.00"), "RON")


def test_amount_without_decimals_still_reads_the_groups() -> None:
    assert parse_amount("garantia este de 27.000 lei") == (Decimal("27000"), "RON")


def test_the_largest_amount_wins_not_the_first() -> None:
    """The sentence names the period and the contract count before the sum."""
    sentence = (
        "in ultimii 3 ani, in cadrul a maxim 2 contracte, a caror valoare cumulata "
        "sa fie cel putin egala cu 1.804.000,00 lei, exclusiv TVA"
    )
    assert parse_amount(sentence) == (Decimal("1804000.00"), "RON")


def test_years_and_counts_are_not_money() -> None:
    assert parse_amount("ultimele 3 exercitii financiare (2023, 2024, 2025)") is None


def test_a_sentence_with_no_figure_returns_none_not_zero() -> None:
    """Zero would pass every gate. None makes the engine answer CHECK."""
    assert parse_amount("cifra de afaceri corespunzatoare valorii estimate") is None


def test_euro_is_reported_as_its_own_currency() -> None:
    assert parse_amount("valoare de 250.000 EUR") == (Decimal("250000"), "EUR")


def test_a_bare_number_needs_a_currency_or_grouping_to_count_as_money() -> None:
    """Found by this suite: 2023/2024/2025 all sat above the plausibility floor."""
    assert parse_amount("exercitiile 2023, 2024, 2025") is None
    assert parse_amount("suma de 27000 lei") == (Decimal("27000"), "RON")
