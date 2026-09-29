"""Turn portal text into facts that keep their quote."""

from bidscout.extract.gates import extract_requirements
from bidscout.extract.html import strip_html
from bidscout.extract.money import parse_amount

__all__ = ["extract_requirements", "parse_amount", "strip_html"]
