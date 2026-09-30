"""Compare the extractor against the labels and print the result as a table.

Two numbers per requirement kind, because they fail in different ways and a
single "accuracy" figure would hide both:

* **coverage** — of the notices where a person could read a figure, how often
  does the extractor find one at all. This is the number the 20 September
  spike guessed at 60%.
* **precision** — of the figures it does find, how often is the figure right.

Three failure counts sit next to them, and they are counted separately on
purpose. A miss costs an opportunity; an invented number can cost a bid,
because a number the buyer never wrote can push a verdict to NO-GO. Ground
rule 2 says that must never happen, so it gets its own column.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bidscout.accuracy.cases import EvalCase
from bidscout.extract.gates import FIELD_MAP, NUMERIC_KINDS, extract_requirements


@dataclass
class GateResult:
    """The tally for one requirement kind across every labelled case."""

    kind: str
    stated: int = 0
    """Cases where the labeller says the buyer states this requirement."""
    with_figure: int = 0
    """Of those, the cases where the labeller could read a figure."""
    found: int = 0
    """Of ``with_figure``, the cases where the extractor produced a figure."""
    right: int = 0
    """Of ``found``, the cases where the figure matches the label."""
    missed: int = 0
    """Cases where the buyer states the requirement and the extractor saw none."""
    invented: int = 0
    """Cases where the extractor produced a figure the labeller says is not there."""
    spurious: int = 0
    """Cases where the extractor reported a requirement the buyer does not state."""

    @property
    def coverage(self) -> float | None:
        """None means "nothing to cover", which is not the same as zero."""
        return None if self.with_figure == 0 else self.found / self.with_figure

    @property
    def precision(self) -> float | None:
        return None if self.found == 0 else self.right / self.found

    @property
    def wrong(self) -> int:
        return self.found - self.right


@dataclass
class Report:
    """Everything one ``bidscout eval`` run measured."""

    gates: dict[str, GateResult] = field(default_factory=dict)
    counted: list[str] = field(default_factory=list)
    unlabelled: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.counted


def measure(cases: list[EvalCase]) -> Report:
    """Run the extractor over every labelled case and tally the differences.

    An unlabelled case is listed, never scored. Counting it as correct would
    let the coverage figure rise every time somebody captured a new notice,
    which is exactly backwards.
    """
    report = Report(gates={kind: GateResult(kind=kind) for kind in FIELD_MAP})

    for case in cases:
        if not case.labelled:
            report.unlabelled.append(case.name)
            continue
        report.counted.append(case.name)
        found = {req.kind: req for req in extract_requirements(case.section3)}
        for kind in sorted(set(case.labels) | set(found)):
            result = report.gates.setdefault(kind, GateResult(kind=kind))
            _tally(result, case.labels.get(kind), found.get(kind))

    return report


def _tally(result: GateResult, label: object, requirement: object) -> None:
    """Score one (kind, case) pair. Kept separate so each branch is readable."""
    label_amount = getattr(label, "amount", None)
    req_amount = getattr(requirement, "amount", None)

    if label is None:
        # The buyer does not state this requirement at all.
        if requirement is not None:
            result.spurious += 1
            if req_amount is not None:
                result.invented += 1
        return

    result.stated += 1
    if requirement is None:
        result.missed += 1
        return

    if label_amount is None:
        # The buyer states the rule but writes no figure. Reporting the
        # requirement is right; reporting a number for it is an invention.
        if req_amount is not None:
            result.invented += 1
        return

    result.with_figure += 1
    if req_amount is None:
        return
    result.found += 1
    if req_amount == label_amount and _currency_agrees(label, requirement):
        result.right += 1


def _currency_agrees(label: object, requirement: object) -> bool:
    """A label with no currency accepts any; a stated one must match.

    The money reader assumes RON when the buyer names no unit, so most labels
    leave the currency out. A label that does name EUR is checked, because a
    EUR threshold read as RON is off by a factor of five.
    """
    wanted = getattr(label, "currency", None)
    return not wanted or str(wanted).upper() == str(getattr(requirement, "currency", "")).upper()


_HEADER = (
    f"{'gate':<18}{'stated':>7}{'figure':>7}{'found':>7}{'cover':>7}"
    f"{'right':>7}{'prec':>7}{'missed':>7}{'invent':>7}{'spur':>7}"
)


def format_report(report: Report) -> str:
    """Render the report as plain text, wide enough for 100 columns."""
    if report.is_empty:
        lines = ["No labelled cases. Nothing was measured."]
        if report.unlabelled:
            lines.append(_unlabelled_line(report))
        lines.append(_help_line())
        return "\n".join(lines)

    lines = [_HEADER, "-" * len(_HEADER)]
    for kind in sorted(report.gates, key=_kind_order):
        result = report.gates[kind]
        if result.stated == 0 and result.spurious == 0:
            continue
        lines.append(_row(result))

    lines.append("")
    lines.append(f"{len(report.counted)} labelled cases measured.")
    if report.unlabelled:
        lines.append(_unlabelled_line(report))
    lines.extend(_legend())
    return "\n".join(lines)


def _row(result: GateResult) -> str:
    return (
        f"{result.kind:<18}{result.stated:>7}{result.with_figure:>7}{result.found:>7}"
        f"{_percent(result.coverage):>7}{result.right:>7}{_percent(result.precision):>7}"
        f"{result.missed:>7}{result.invented:>7}{result.spurious:>7}"
    )


def _kind_order(kind: str) -> tuple[int, str]:
    """Numeric gates first: they are the ones the two percentages are about."""
    return (0 if kind in NUMERIC_KINDS else 1, kind)


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{round(100 * value)}%"


def _unlabelled_line(report: Report) -> str:
    return (
        f"{len(report.unlabelled)} case(s) not labelled yet and therefore not counted: "
        f"{', '.join(sorted(report.unlabelled))}"
    )


def _help_line() -> str:
    return (
        "Capture one with `bidscout capture <c-notice-id>`, fill in the labels, "
        "set labelled to true, and run this again."
    )


def _legend() -> list[str]:
    return [
        "",
        "stated   the buyer asks for this, according to the person who labelled the case",
        "figure   of those, the cases where a person could read an actual number",
        "cover    of `figure`, how often the extractor found a number at all",
        "prec     of the numbers it found, how often the number was right",
        "missed   the buyer asks for it and the extractor reported nothing",
        "invent   the extractor produced a number the buyer never wrote  <- the dangerous one",
        "spur     the extractor reported a requirement the buyer does not state",
    ]
