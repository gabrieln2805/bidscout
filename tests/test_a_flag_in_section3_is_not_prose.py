"""The live portal sends some Section 3 fields as booleans.

Found on the first live score, 2 October 2026: ``mandatoryProfesionalQualif``
arrived as ``true`` or ``false`` on all 44 contract notices, and the HTML
stripper raised ``TypeError`` on the first one, ending the whole run.
"""

from __future__ import annotations

from bidscout.extract.gates import extract_requirements
from bidscout.models import Section3


def test_a_boolean_field_reads_as_no_text() -> None:
    section = Section3("1", {"mandatoryProfesionalQualif": True, "isReservedContract": False})
    assert section.text("mandatoryProfesionalQualif") == ""
    assert section.text("isReservedContract") == ""


def test_a_section_with_a_flag_still_yields_its_prose(section3_full) -> None:
    raw = {**section3_full.raw, "mandatoryProfesionalQualif": True}
    kinds = {req.kind for req in extract_requirements(Section3("1096282", raw))}
    assert "turnover" in kinds
    assert "qualification" not in kinds
