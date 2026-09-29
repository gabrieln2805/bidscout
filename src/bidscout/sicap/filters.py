"""Guard the filter names we send to the portal.

The portal ignores a key it does not know and returns the unfiltered set. So
a misspelled filter does not fail — it quietly matches the whole market. The
spike on 20 September 2026 found five such names on the notice endpoint and
four on the direct-acquisition endpoint. They are listed here by name so that
a future session cannot lose that finding again.

Rule: a filter is allowed only after a test showed the result count change.
"""

from __future__ import annotations

from bidscout.errors import UnknownFilter

#: Keys that are part of every request body and are not filters.
ENVELOPE: frozenset[str] = frozenset(
    {"pageIndex", "pageSize", "sortProperties", "sysNoticeTypeIds", "hasUnansweredQuestions"}
)

#: Notice-search filters proven to change the result count.
NOTICE_FILTERS: frozenset[str] = frozenset(
    {
        "startPublicationDate",
        "endPublicationDate",
        "startTenderReceiptDeadline",
        "endTenderReceiptDeadline",
        "cPVId",
        "sysProcedureTypeId",
        "sysProcedureStateId",
        "contractingAuthorityId",
        "noticeNumber",
    }
)

#: Names the notice endpoint accepts and then ignores. Sending one is a bug.
NOTICE_IGNORED: frozenset[str] = frozenset(
    {"cpvCode", "cpvCodeId", "cpvCategoryId", "contractTitle", "publicationDateStart"}
)

#: Direct-acquisition filters proven to change the result set.
DA_FILTERS: frozenset[str] = frozenset(
    {
        "finalizationDateStart",
        "finalizationDateEnd",
        "sysDirectAcquisitionStateId",
        "uniqueIdentificationCode",
        "supplierId",
    }
)

#: Names the direct-acquisition endpoint ignores. Still open: the real
#: publication-date and CPV filters for this endpoint are not known yet.
DA_IGNORED: frozenset[str] = frozenset(
    {"startPublicationDate", "publicationDateStart", "dateFrom", "cPVId"}
)

_ALLOWED: dict[str, frozenset[str]] = {
    "notice": NOTICE_FILTERS | ENVELOPE,
    "direct_acquisition": DA_FILTERS | ENVELOPE,
}

_IGNORED: dict[str, frozenset[str]] = {
    "notice": NOTICE_IGNORED,
    "direct_acquisition": DA_IGNORED,
}


def validate_filters(body: dict[str, object], endpoint: str) -> None:
    """Raise ``UnknownFilter`` unless every key in ``body`` is known to work.

    ``endpoint`` is ``"notice"`` or ``"direct_acquisition"``. A key that the
    portal is known to ignore produces a message that says so, because that is
    the case a reader is most likely to mistake for a working query.
    """
    allowed = _ALLOWED[endpoint]
    ignored = _IGNORED[endpoint]
    for key in body:
        if key in ignored:
            raise UnknownFilter(
                f"{key!r} is accepted by the {endpoint} endpoint and then ignored. "
                f"The portal would return the unfiltered set. Use one of: "
                f"{', '.join(sorted(_ALLOWED[endpoint] - ENVELOPE))}."
            )
        if key not in allowed:
            raise UnknownFilter(
                f"{key!r} is not a tested filter for the {endpoint} endpoint. "
                f"Prove it changes the result count, then add it to filters.py."
            )
