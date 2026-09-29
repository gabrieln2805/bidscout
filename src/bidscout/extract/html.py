"""Strip the HTML the portal puts inside its JSON fields.

Section 3 values are HTML fragments, not plain text. They carry ``<br>``,
``<p>``, ``&nbsp;`` and inline bold tags around the very numbers we need. A
naive ``re.sub("<[^>]*>", "")`` joins words across a removed block tag and
turns "3 exercitii<br>financiare" into "exercitiifinanciare", which then
fails to match. So block tags become a space before anything is removed.
"""

from __future__ import annotations

import html
import re

#: Tags that separate words even though they carry no text of their own.
_BLOCK_TAG = re.compile(r"(?i)</?(br|p|div|li|tr|td|th|ul|ol|table|h[1-6])\b[^>]*>")
_ANY_TAG = re.compile(r"<[^>]*>")
_WHITESPACE = re.compile(r"[ \t\r\f\v ]+")


def strip_html(value: str) -> str:
    """Return ``value`` as plain text with tidy single spaces.

    Entities are unescaped after the tags are removed, so that a literal
    ``&lt;b&gt;`` written by the buyer is not mistaken for markup.
    """
    if not value:
        return ""
    text = _BLOCK_TAG.sub(" ", value)
    text = _ANY_TAG.sub("", text)
    text = html.unescape(text)
    text = text.replace(" ", " ")
    text = _WHITESPACE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()
