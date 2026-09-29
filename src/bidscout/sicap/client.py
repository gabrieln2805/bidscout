"""The single module that knows a SEAP URL.

Everything else in bidscout receives data from here and never builds a
request of its own. That keeps the portal's oddities in one file: the cap
that looks like a count, the filters that are silently ignored, and the
server clock that must be preferred over the local one.

The client is deliberately slow and polite: one request at a time, a small
pause between them, and a User-Agent that names the project.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any, Protocol

from bidscout.errors import NoticeNotFound, SearchTooWide
from bidscout.sicap.filters import validate_filters

BASE_URL = "https://www.e-licitatie.ro/api-pub/"

#: The portal caps a wide notice search here and sets ``searchTooLong``.
NOTICE_CAP = 3000
#: The same cap on the direct-acquisition endpoint.
DA_CAP = 2000

#: ``sysNoticeTypeId`` for a full contract notice. Simplified notices use 17
#: and have no working detail view yet — see docs/data-sources.md, open item 1.
NOTICE_TYPE_FULL = 2
NOTICE_TYPE_SIMPLIFIED = 17

USER_AGENT = "bidscout/0.3 (public tender decision aid; contact: see repository README)"


class Transport(Protocol):
    """The small slice of ``requests`` that the client actually uses.

    Injecting this is what lets the whole test suite run offline: a test hands
    in a transport built from captured fixtures, and no socket is opened.
    """

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any: ...

    def post(self, url: str, json: dict[str, Any] | None = None) -> Any: ...


class RequestsTransport:
    """The real transport. Imported lazily so tests never need ``requests``."""

    def __init__(self, timeout: float = 30.0) -> None:
        import requests  # noqa: PLC0415 - kept local so offline tests need no install

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self._timeout = timeout

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response

    def post(self, url: str, json: dict[str, Any] | None = None) -> Any:
        # The portal rejects a POST without this content type, and the error it
        # returns does not say so. Set it explicitly rather than rely on a default.
        response = self._session.post(
            url, json=json, timeout=self._timeout, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response


class SicapClient:
    """Read-only access to the public SICAP JSON API."""

    def __init__(
        self,
        transport: Transport | None = None,
        base_url: str = BASE_URL,
        pause_seconds: float = 0.4,
    ) -> None:
        self._transport = transport if transport is not None else RequestsTransport()
        self._base_url = base_url.rstrip("/") + "/"
        self._pause_seconds = pause_seconds
        self._last_call: float = 0.0

    # ---------------------------------------------------------------- plumbing

    def _wait_turn(self) -> None:
        """Keep at least ``pause_seconds`` between two calls to the portal."""
        elapsed = time.monotonic() - self._last_call
        if self._last_call and elapsed < self._pause_seconds:
            time.sleep(self._pause_seconds - elapsed)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._wait_turn()
        return self._transport.get(self._base_url + path, params=params).json()

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        self._wait_turn()
        return self._transport.post(self._base_url + path, json=body).json()

    # ------------------------------------------------------------------ search

    def search_notices(self, **filters: Any) -> dict[str, Any]:
        """Search contract notices. Raises ``SearchTooWide`` when capped.

        The caller passes filters by keyword. Every name is checked against the
        tested list first, because an unknown name would widen the search
        instead of failing.
        """
        body: dict[str, Any] = {
            "sysNoticeTypeIds": [],
            "sortProperties": [{"sortProperty": "noticeStateDate", "descending": True}],
            "pageSize": 200,
            "pageIndex": 0,
            "hasUnansweredQuestions": False,
        }
        body.update(filters)
        validate_filters(body, "notice")
        payload = self._post("NoticeCommon/GetCNoticeList/", body)
        _refuse_capped_result(payload, NOTICE_CAP)
        return payload

    def iter_notices(self, page_size: int = 200, **filters: Any) -> Iterator[dict[str, Any]]:
        """Yield every notice matching ``filters``, one page at a time."""
        page = 0
        while True:
            payload = self.search_notices(pageSize=page_size, pageIndex=page, **filters)
            items = payload.get("items") or []
            yield from items
            if len(items) < page_size:
                return
            page += 1

    def list_direct_acquisitions(self, **filters: Any) -> dict[str, Any]:
        """Search direct acquisitions — the high-volume, low-value channel."""
        body: dict[str, Any] = {"pageSize": 200, "pageIndex": 0, "sortProperties": []}
        body.update(filters)
        validate_filters(body, "direct_acquisition")
        payload = self._post(
            "DirectAcquisitionCommon/GetDirectAcquisitionList/",
            body,
        )
        _refuse_capped_result(payload, DA_CAP)
        return payload

    # ------------------------------------------------------------------ detail

    def get_notice_view(self, c_notice_id: int | str) -> dict[str, Any]:
        """Fetch the notice header. Raises ``NoticeNotFound`` when null.

        The portal answers with ``null`` rather than a 404 for a simplified
        notice, so a caller that trusted the status code would carry a ``None``
        into the parser and fail far from the cause.
        """
        payload = self._get(
            "PUBLICCNotice/getPubCNoticeView/", {"cNoticeId": c_notice_id}
        )
        if payload is None:
            raise NoticeNotFound(
                f"the portal returned null for cNoticeId={c_notice_id}. "
                "Simplified notices (sysNoticeTypeId 17, prefix SCN) have no "
                "working detail view yet."
            )
        return payload

    def get_section3(
        self, init_notice_id: int | str, notice_type: int = NOTICE_TYPE_FULL
    ) -> dict[str, Any]:
        """Fetch Section 3 — the qualification criteria, as HTML in JSON.

        This is the section that carries the turnover and experience gates, so
        most decisions never need to open a PDF.
        """
        payload = self._get(
            "NoticeCommon/GetSection3View/",
            {"initNoticeId": init_notice_id, "sysNoticeTypeId": notice_type},
        )
        if payload is None:
            raise NoticeNotFound(f"no Section 3 for initNoticeId={init_notice_id}")
        return payload

    def get_documents(
        self, init_notice_id: int | str, notice_type: int = NOTICE_TYPE_FULL
    ) -> dict[str, Any]:
        """List the files attached to a notice, grouped by kind."""
        return self._get(
            "NoticeCommon/GetDfNoticeSectionFiles/",
            {"initNoticeId": init_notice_id, "sysNoticeTypeId": notice_type},
        )

    def download_document(self, guid_or_url: str) -> bytes:
        """Download one attached file by its GUID.

        A GUID never changes, so the caller may cache the bytes for ever. The
        response carries ``application/octet-stream`` whatever the real type
        is, so the caller must read the extension and sniff the magic bytes.
        """
        path = guid_or_url.split("api-pub/", 1)[-1]
        if not path.startswith("files/noticedoc/"):
            path = f"files/noticedoc/{path}"
        self._wait_turn()
        return self._transport.get(self._base_url + path).content

    # --------------------------------------------------------------- reference

    def search_cpv(self, text: str) -> list[dict[str, Any]]:
        """Look a CPV code up and get the numeric ``cpvCodeID`` the filter needs."""
        return self._get("Cpv/SearchCpv", {"text": text})

    def server_time(self) -> str:
        """The portal's own clock. Use it for deadline maths, not the local clock."""
        payload = self._get("time/getServerTime/")
        if isinstance(payload, dict):
            return str(payload.get("serverTime") or payload.get("value") or payload)
        return str(payload)


def _refuse_capped_result(payload: dict[str, Any], cap: int) -> None:
    """Raise ``SearchTooWide`` when the portal returned a cap, not a count.

    Checked both ways round: the flag alone is enough, and so is a total that
    sits exactly on the cap. Older responses have been seen with one but not
    the other, and either way the tail of the result set is missing.
    """
    total = payload.get("total")
    if payload.get("searchTooLong") or (isinstance(total, int) and total >= cap):
        raise SearchTooWide(
            f"the portal capped this search at {total}. That is a cap, not a count. "
            "Narrow the date window and search again."
        )
