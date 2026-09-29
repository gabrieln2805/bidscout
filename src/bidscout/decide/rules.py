"""Load the rule set from YAML.

The rules live outside the code so that a bid consultant can correct a gate
without a Python change, and so that a second sector is a new file rather
than a new release. This module only validates the shape; the meaning lives
in ``engine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Gate:
    """One hard gate: a requirement kind measured against a profile figure."""

    kind: str
    profile_key: str
    label: str


@dataclass
class RuleSet:
    """Everything the engine needs, read from one YAML file."""

    name: str
    gates: list[Gate] = field(default_factory=list)
    weights: dict[str, int] = field(default_factory=dict)
    go_threshold: int = 60

    @property
    def total_weight(self) -> int:
        """The weights need not add to 100; the score is normalised to them."""
        return sum(self.weights.values()) or 1


def load_rules(path: str | Path) -> RuleSet:
    """Read a rule file and fail loudly on a shape the engine cannot use."""
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    gates = [
        Gate(
            kind=str(item["kind"]),
            profile_key=str(item["profile"]),
            label=str(item.get("label", item["kind"])),
        )
        for item in data.get("hard_gates", [])
    ]
    weights = {str(k): int(v) for k, v in (data.get("weights") or {}).items()}
    return RuleSet(
        name=str(data.get("name", "unnamed")),
        gates=gates,
        weights=weights,
        go_threshold=int(data.get("go_threshold", 60)),
    )


def load_profile(path: str | Path) -> dict[str, Any]:
    """Read the company profile. Money values become ``Decimal``.

    YAML would otherwise give a float, and a float comparison against a
    Decimal requirement raises, which is a poor way to learn about a typo.
    """
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {key: _as_decimal_if_money(key, value) for key, value in data.items()}


def _as_decimal_if_money(key: str, value: Any) -> Any:
    if key.endswith("_ron") and isinstance(value, int | float | str):
        return Decimal(str(value))
    return value
