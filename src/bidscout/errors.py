"""One error type for each way the portal can mislead us.

Each class here marks a trap that cost real time during the data spike. They
are separate types so that a caller can react differently: a too-wide search
is retryable with a narrower window, an unknown filter is a programming
mistake that must never reach the portal.
"""


class BidscoutError(Exception):
    """Base class, so a caller can catch everything this package raises."""


class UnknownFilter(BidscoutError):
    """A filter name the portal does not honour was put in a request body.

    The portal answers an unknown key with the *unfiltered* set instead of an
    error. A typo would therefore look like a working query that suddenly
    matches the whole market. We refuse to send the request at all.
    """


class SearchTooWide(BidscoutError):
    """The portal capped the result set, so ``total`` is not a real count.

    A wide search comes back with ``total: 3000`` and ``searchTooLong: true``.
    Treating that as a count silently loses every notice past the cap, so the
    caller must narrow the date window and ask again.
    """


class NoticeNotFound(BidscoutError):
    """The portal has no detail view for this notice id or notice type."""


class SectionNotStored(BidscoutError):
    """We were asked to work from a notice's Section 3 and have none on file.

    Distinct from ``NoticeNotFound``: the portal may well have the section, we
    simply have not fetched it. Saying so is better than carrying an empty
    payload forward, which would look like a buyer who asks for nothing.
    """
