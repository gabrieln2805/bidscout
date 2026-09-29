"""Map one row of GetCNoticeList onto a Notice without losing anything."""

from decimal import Decimal

from bidscout.pipeline import notice_from_item


def test_the_named_fields_are_copies_not_the_only_copy(notice_item) -> None:
    notice = notice_from_item(notice_item)
    assert notice.notice_no == "CN1096282"
    assert notice.buyer == "COMUNA CHETANI"
    assert notice.estimated_value_ron == Decimal("1804000.0")
    assert notice.raw is notice_item


def test_the_cpv_is_cut_down_to_the_bare_code(notice_item) -> None:
    """The portal sends "72000000-5 - Servicii IT...". Only the digits filter."""
    assert notice_from_item(notice_item).cpv == "72000000"


def test_a_simplified_notice_is_recognised_by_its_prefix() -> None:
    notice = notice_from_item({"cNoticeId": 1, "noticeNo": "SCN1234", "sysNoticeTypeId": 17})
    assert notice.is_simplified


def test_a_full_notice_is_not_marked_simplified(notice_item) -> None:
    assert not notice_from_item(notice_item).is_simplified


def test_missing_optional_fields_do_not_raise() -> None:
    notice = notice_from_item({"cNoticeId": 7})
    assert notice.estimated_value_ron is None
    assert notice.cpv is None
