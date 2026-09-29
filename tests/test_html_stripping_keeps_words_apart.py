"""Section 3 values are HTML fragments, and the tags sit around the numbers."""

from bidscout.extract.html import strip_html


def test_block_tags_become_a_space_not_nothing() -> None:
    """Removing <br> without a space joins two words into one unreadable token."""
    assert strip_html("ultimele 3 exercitii<br>financiare") == "ultimele 3 exercitii financiare"


def test_inline_bold_around_a_number_is_removed_cleanly() -> None:
    assert strip_html("egala cu <b>2.700.000,00 Lei</b>.") == "egala cu 2.700.000,00 Lei."


def test_entities_are_unescaped_after_the_tags_are_gone() -> None:
    assert strip_html("exerci&#539;ii") == "exerciții"


def test_non_breaking_space_becomes_an_ordinary_space() -> None:
    assert strip_html("2.700.000,00&nbsp;Lei") == "2.700.000,00 Lei"


def test_empty_input_is_an_empty_string_not_none() -> None:
    assert strip_html("") == ""
