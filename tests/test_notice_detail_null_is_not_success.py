"""The portal answers a simplified notice with ``null``, not a 404.

A caller that trusted the status code would carry a ``None`` into the parser
and fail far away from the cause.
"""

from typing import Any

import pytest

from bidscout.errors import NoticeNotFound
from bidscout.sicap.client import SicapClient


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.content = b"file-bytes"

    def json(self) -> Any:
        return self._payload


class _Transport:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get(self, url: str, params: Any = None) -> Any:
        self.urls.append(url)
        return _Response(self.payload)

    def post(self, url: str, json: Any = None) -> Any:
        self.urls.append(url)
        return _Response(self.payload)


def test_null_notice_view_raises_a_named_error() -> None:
    client = SicapClient(transport=_Transport(None), pause_seconds=0.0)
    with pytest.raises(NoticeNotFound, match="SCN"):
        client.get_notice_view("SCN1234")


def test_null_section3_raises_too() -> None:
    client = SicapClient(transport=_Transport(None), pause_seconds=0.0)
    with pytest.raises(NoticeNotFound):
        client.get_section3("1096282")


def test_document_download_accepts_a_bare_guid_or_a_full_path() -> None:
    """The file list gives a path; a stored row gives only the GUID."""
    transport = _Transport({})
    client = SicapClient(transport=transport, pause_seconds=0.0)
    client.download_document("28c82dc9e28547f795cc5ac9553e5a35")
    client.download_document("api-pub/files/noticedoc/28c82dc9e28547f795cc5ac9553e5a35")
    assert transport.urls[0] == transport.urls[1]
