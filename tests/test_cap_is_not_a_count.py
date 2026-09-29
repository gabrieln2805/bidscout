"""``total: 3000`` with ``searchTooLong`` is a cap, not a count.

Reading it as a count silently drops every notice past the cap, so the
client refuses the whole response and asks the caller to narrow the window.
"""

from typing import Any

import pytest

from bidscout.errors import SearchTooWide
from bidscout.sicap.client import SicapClient


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.content = b""

    def json(self) -> Any:
        return self._payload


class _FakeTransport:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Any]] = []

    def get(self, url: str, params: Any = None) -> Any:
        self.calls.append((url, params))
        return _FakeResponse(self.payload)

    def post(self, url: str, json: Any = None) -> Any:
        self.calls.append((url, json))
        return _FakeResponse(self.payload)


def _client(payload: Any) -> tuple[SicapClient, _FakeTransport]:
    transport = _FakeTransport(payload)
    return SicapClient(transport=transport, pause_seconds=0.0), transport


def test_search_too_long_flag_is_refused() -> None:
    client, _ = _client({"total": 3000, "items": [], "searchTooLong": True})
    with pytest.raises(SearchTooWide, match="cap, not a count"):
        client.search_notices(startPublicationDate="2020-01-01")


def test_total_on_the_cap_is_refused_even_without_the_flag() -> None:
    """Responses have been seen with the total at the cap and the flag absent."""
    client, _ = _client({"total": 3000, "items": [], "searchTooLong": False})
    with pytest.raises(SearchTooWide):
        client.search_notices(startPublicationDate="2020-01-01")


def test_a_result_under_the_cap_is_a_real_count() -> None:
    client, _ = _client({"total": 378, "items": [{"noticeNo": "CN1"}], "searchTooLong": False})
    payload = client.search_notices(startPublicationDate="2026-09-15")
    assert payload["total"] == 378


def test_search_sorts_newest_first_by_default() -> None:
    client, transport = _client({"total": 1, "items": [], "searchTooLong": False})
    client.search_notices()
    _, body = transport.calls[0]
    assert body["sortProperties"] == [{"sortProperty": "noticeStateDate", "descending": True}]
