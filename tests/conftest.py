"""Shared fixtures. Everything here is offline by design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bidscout.decide.rules import RuleSet, load_rules
from bidscout.models import Section3

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def section3_full() -> Section3:
    """A notice whose turnover and experience gates are both measurable."""
    return Section3(init_notice_id="1096282", raw=load_fixture("section3_cn1096282.json"))


@pytest.fixture
def section3_vague() -> Section3:
    """A notice that states a turnover rule but names no figure."""
    return Section3(init_notice_id="1096999", raw=load_fixture("section3_vague.json"))


@pytest.fixture
def notice_item() -> dict[str, Any]:
    return load_fixture("notice_item.json")


@pytest.fixture
def rules() -> RuleSet:
    return load_rules(Path(__file__).parents[1] / "rules" / "it.yaml")


@pytest.fixture
def strong_profile() -> dict[str, Any]:
    """A company that clears every gate in the full fixture with room to spare."""
    return {
        "company_name": "Strong SRL",
        "average_turnover_ron": 6000000,
        "similar_experience_ron": 4000000,
        "available_guarantee_ron": 100000,
        "min_contract_ron": 50000,
        "max_contract_ron": 3000000,
        "cpv_watchlist": ["72000000"],
    }


@pytest.fixture
def small_profile() -> dict[str, Any]:
    """A company whose turnover is genuinely below the stated threshold."""
    return {
        "company_name": "Small SRL",
        "average_turnover_ron": 1200000,
        "similar_experience_ron": 4000000,
        "available_guarantee_ron": 100000,
        "min_contract_ron": 50000,
        "max_contract_ron": 3000000,
        "cpv_watchlist": ["72000000"],
    }
