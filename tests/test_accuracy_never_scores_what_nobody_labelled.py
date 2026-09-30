"""The accuracy harness must not flatter itself.

Every test here guards one way a harness can report a good number it has not
earned: by counting an unlabelled case as correct, by treating an invented
figure as a find, or by printing 0% where the honest answer is "there was
nothing to measure".
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from bidscout.accuracy.cases import EvalCase, Label, load_case, load_cases
from bidscout.accuracy.report import format_report, measure
from bidscout.models import Section3

CASE_DIR = Path(__file__).parents[1] / "eval" / "cases"


def _case(name: str, raw: dict, labels: dict[str, Label], labelled: bool = True) -> EvalCase:
    return EvalCase(
        name=name,
        section3=Section3(init_notice_id=name, raw=raw),
        labels=labels,
        labelled=labelled,
    )


def test_an_unlabelled_case_is_listed_and_never_counted() -> None:
    """Otherwise every capture would raise the score without anybody checking it."""
    report = measure(
        [_case("fresh", {"efCriteriaMin": "<p>1.000.000,00 lei</p>"}, {}, labelled=False)]
    )
    assert report.counted == []
    assert report.unlabelled == ["fresh"]
    assert report.gates["turnover"].stated == 0
    assert "not labelled yet" in format_report(report)


def test_a_figure_where_the_buyer_wrote_none_is_counted_as_invented() -> None:
    """This is the failure that can push a verdict to NO-GO on a number nobody wrote."""
    report = measure(
        [
            _case(
                "vague",
                {"efCriteriaMin": "<p>cifra de afaceri de minimum 2.000.000,00 lei</p>"},
                {"turnover": Label("turnover", amount=None)},
            )
        ]
    )
    turnover = report.gates["turnover"]
    assert turnover.stated == 1
    assert turnover.invented == 1
    # It is not a coverage failure: there was no figure to cover in the first place.
    assert turnover.with_figure == 0
    assert turnover.coverage is None


def test_a_requirement_the_extractor_did_not_see_is_missed_not_wrong() -> None:
    report = measure(
        [_case("blank", {}, {"turnover": Label("turnover", amount=Decimal("500000"))})]
    )
    turnover = report.gates["turnover"]
    assert (turnover.missed, turnover.found, turnover.wrong) == (1, 0, 0)


def test_a_requirement_the_buyer_does_not_state_is_counted_as_spurious() -> None:
    report = measure([_case("extra", {"depositsAndWarranties": "<p>garantia</p>"}, {})])
    assert report.gates["deposit"].spurious == 1


def test_a_wrong_figure_lowers_precision_and_not_coverage() -> None:
    """Coverage says "we found something"; precision says "it was right"."""
    report = measure(
        [
            _case(
                "off",
                {"efCriteriaMin": "<p>minimum 1.804.000,00 lei</p>"},
                {"turnover": Label("turnover", amount=Decimal("2700000.00"))},
            )
        ]
    )
    turnover = report.gates["turnover"]
    assert turnover.coverage == 1.0
    assert turnover.precision == 0.0
    assert turnover.wrong == 1


def test_a_currency_the_label_names_must_match() -> None:
    """A EUR threshold read as RON is off by roughly five, with the right digits."""
    report = measure(
        [
            _case(
                "eur",
                {"depositsAndWarranties": "<p>garantia este de 4.500,00 lei</p>"},
                {"deposit": Label("deposit", amount=Decimal("4500.00"), currency="EUR")},
            )
        ]
    )
    deposit = report.gates["deposit"]
    assert deposit.found == 1
    assert deposit.right == 0


def test_nothing_to_measure_prints_a_dash_and_not_a_percentage() -> None:
    """0% means the extractor failed. "-" means nobody has given it a chance yet."""
    report = measure([_case("text-only", {"personalSituation": "<p>art. 164</p>"},
                            {"personal_situation": Label("personal_situation")})])
    assert report.gates["personal_situation"].coverage is None
    assert " -" in format_report(report)


def test_an_empty_case_set_reports_nothing_rather_than_a_perfect_score() -> None:
    report = measure([])
    assert report.is_empty
    assert "Nothing was measured" in format_report(report)


def test_a_label_amount_written_as_a_json_number_is_refused(tmp_path) -> None:
    """json reads an unquoted 2700000.10 as a float, which is not what was typed."""
    path = tmp_path / "loose.json"
    path.write_text(
        json.dumps(
            {
                "labelled": True,
                "labels": {"turnover": {"amount": 2700000.10}},
                "section3_raw": {"efCriteriaMin": "<p>x</p>"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Quote it as a string"):
        load_case(path)


def test_a_case_file_without_its_raw_payload_is_refused(tmp_path) -> None:
    """Ground rule 3: a case that dropped section3_raw cannot be replayed."""
    path = tmp_path / "hollow.json"
    path.write_text(json.dumps({"labelled": True, "labels": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="section3_raw"):
        load_case(path)


def test_the_repository_case_set_loads_and_invents_nothing() -> None:
    """The figure `bidscout eval` prints today, guarded so a parser change shows up."""
    cases = load_cases(CASE_DIR)
    assert cases, f"no labelled cases in {CASE_DIR}"
    report = measure(cases)
    assert report.counted, "the shipped case set must contain labelled cases"
    for result in report.gates.values():
        assert result.invented == 0, f"{result.kind}: a figure was invented"
        assert result.spurious == 0, f"{result.kind}: a requirement was reported unasked"
        assert result.wrong == 0, f"{result.kind}: a figure was read wrongly"
