"""Labelled Section 3 cases: the input the accuracy harness measures against.

A case file holds two things that must never be mixed up: the portal's raw
Section 3 exactly as it arrived (ground rule 3 — it is kept for ever, so a
parser rewrite is replayed from disk) and the *labels*, which are what a
person reads in that payload. The labels are written by hand. A harness that
labels its own input measures nothing.

``labelled: false`` is an honest state, not an error. ``bidscout capture``
writes a case with no labels; until somebody fills them in, the harness
counts the case as unlabelled and leaves it out of the figures rather than
scoring it as correct.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from bidscout.models import Section3

#: Where the labelled set lives. Deliberately not under ``data/``: these files
#: are part of the repository, because a measurement nobody else can repeat is
#: not a measurement.
DEFAULT_CASE_DIR = Path("eval") / "cases"


@dataclass(frozen=True)
class Label:
    """What a person reads for one requirement kind in one notice.

    ``amount is None`` is a real answer and not a missing one: it means the
    buyer states the requirement but names no figure a machine can read
    ("o cifra de afaceri corespunzatoare valorii estimate"). For such a case
    the extractor is expected to report the requirement *and* to report no
    number. A number there is an invention, which is the worst failure this
    harness looks for — it is what turned the years "2023, 2024, 2025" into a
    2,025 RON turnover threshold before the suite caught it.
    """

    kind: str
    amount: Decimal | None = None
    currency: str | None = None


@dataclass
class EvalCase:
    """One notice's Section 3 plus the hand-written truth about it."""

    name: str
    section3: Section3
    labels: dict[str, Label] = field(default_factory=dict)
    labelled: bool = False
    path: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def load_case(path: str | Path) -> EvalCase:
    """Read one case file and fail loudly on a shape the harness cannot use."""
    path = Path(path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("section3_raw")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: no section3_raw object; the raw payload must be kept")

    labels = {
        str(kind): _label_from(str(kind), value, path)
        for kind, value in (data.get("labels") or {}).items()
    }
    return EvalCase(
        name=str(data.get("name") or path.stem),
        section3=Section3(init_notice_id=str(data.get("c_notice_id") or path.stem), raw=raw),
        labels=labels,
        labelled=bool(data.get("labelled", False)),
        path=path,
        meta={k: v for k, v in data.items() if k not in ("section3_raw", "labels")},
    )


def load_cases(directory: str | Path = DEFAULT_CASE_DIR) -> list[EvalCase]:
    """Read every case in ``directory``, in a stable order."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [load_case(path) for path in sorted(directory.glob("*.json"))]


def write_case(
    directory: str | Path,
    name: str,
    section3_raw: dict[str, Any],
    c_notice_id: str,
    notice_no: str | None = None,
) -> Path:
    """Write an unlabelled case, ready for a person to fill the labels in.

    The file is written with the label keys already present and empty so that
    the labeller can see which kinds the harness knows about, and with
    ``labelled: false`` so that an unfinished file cannot quietly inflate a
    coverage figure.
    """
    from bidscout.extract.gates import FIELD_MAP  # noqa: PLC0415 - avoids a cycle

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    body = {
        "name": name,
        "c_notice_id": c_notice_id,
        "notice_no": notice_no or "",
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "labelled": False,
        "label_help": (
            "Read the buyer's own sentence in section3_raw and fill one entry per "
            "requirement the buyer actually states. Delete the kinds the buyer does "
            "not state. Quote every amount as a string, e.g. \"2700000.00\". Leave "
            "amount null when the buyer states the rule but names no figure. "
            "Then set labelled to true."
        ),
        "labels": {kind: {"amount": None, "currency": None} for kind in FIELD_MAP},
        "section3_raw": section3_raw,
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _label_from(kind: str, value: Any, path: Path) -> Label:
    if value is None:
        return Label(kind=kind)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: label {kind!r} must be an object or null")
    currency = value.get("currency")
    return Label(
        kind=kind,
        amount=_label_amount(kind, value.get("amount"), path),
        currency=str(currency) if currency else None,
    )


def _label_amount(kind: str, value: Any, path: Path) -> Decimal | None:
    """Turn a labelled amount into an exact ``Decimal``, refusing a JSON float.

    ``json`` reads an unquoted 2700000.10 as a binary float, and the Decimal
    built from it is not the number the labeller typed. Since the whole point
    of this project is that a number can be checked, a float label is refused
    with an instruction rather than silently rounded.
    """
    if value is None:
        return None
    if isinstance(value, float):
        raise ValueError(
            f"{path}: label {kind!r} has the amount as a JSON number. Quote it as a "
            'string ("2700000.00") so it is read exactly.'
        )
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{path}: label {kind!r} has an unreadable amount {value!r}") from exc
