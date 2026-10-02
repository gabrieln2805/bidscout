"""The portal answers any request without a ``Referer`` with 403.

Found on 2 October 2026, on the first live run this project ever made:

    403 {"message": "Access Denied: Referrer cannot be null."}

It applies to every endpoint, ``getServerTime`` included, so without the header
nothing works at all. This is the "required header" the 20 September spike
recorded as one of three traps and whose name was lost when that session's code
never reached disk — the only one of the three that had no test. Now it has one.
"""

from __future__ import annotations

from bidscout.sicap.client import REFERER, USER_AGENT, RequestsTransport


def test_the_real_transport_sends_a_referer() -> None:
    """Builds a session only; opens no socket, so this runs offline."""
    headers = RequestsTransport()._session.headers
    assert headers["Referer"] == REFERER


def test_the_referer_points_at_the_portal_itself() -> None:
    """An anti-hotlinking check: the request must concern the portal's own site."""
    assert REFERER.startswith("https://www.e-licitatie.ro")


def test_the_client_still_says_what_it_is() -> None:
    """The Referer satisfies a check; it does not disguise the caller.

    If this ever has to become a browser User-Agent, that is a decision to take
    knowingly and write down, not something to let drift in beside a bug fix.
    """
    headers = RequestsTransport()._session.headers
    assert headers["User-Agent"] == USER_AGENT
    assert "bidscout" in headers["User-Agent"]
