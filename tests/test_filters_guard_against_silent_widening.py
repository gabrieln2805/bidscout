"""The portal ignores a filter name it does not know and returns everything.

A typo would therefore look like a working query that matches the whole
market. These tests keep the refusal in place.
"""

import pytest

from bidscout.errors import UnknownFilter
from bidscout.sicap.filters import validate_filters


def test_tested_filter_is_accepted() -> None:
    validate_filters({"startPublicationDate": "2026-09-01", "pageSize": 200}, "notice")


def test_misspelled_filter_is_refused_before_the_request_is_sent() -> None:
    with pytest.raises(UnknownFilter, match="not a tested filter"):
        validate_filters({"startPublicationDat": "2026-09-01"}, "notice")


@pytest.mark.parametrize(
    "name", ["cpvCode", "cpvCodeId", "cpvCategoryId", "contractTitle", "publicationDateStart"]
)
def test_known_ignored_notice_filters_say_so_by_name(name: str) -> None:
    """These five were measured as ignored on 20 September 2026."""
    with pytest.raises(UnknownFilter, match="ignored"):
        validate_filters({name: 1}, "notice")


@pytest.mark.parametrize("name", ["startPublicationDate", "publicationDateStart", "cPVId"])
def test_direct_acquisition_ignores_the_notice_date_filters(name: str) -> None:
    """The same name can work on one endpoint and be ignored on the other."""
    with pytest.raises(UnknownFilter, match="ignored"):
        validate_filters({name: 1}, "direct_acquisition")


def test_finalization_date_is_the_one_that_works_for_direct_acquisitions() -> None:
    validate_filters({"finalizationDateStart": "2026-09-01"}, "direct_acquisition")
