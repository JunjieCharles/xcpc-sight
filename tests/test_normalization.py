import pytest

from core import DataValidationError, DefaultNormalizer
from core.normalization import is_coach_name


def test_normalizer_handles_nfkc_case_punctuation_and_traditional_chinese() -> None:
    normalizer = DefaultNormalizer()
    assert normalizer.member(" Ａlice-ZHANG ") == "alicezhang"
    assert normalizer.school("香港中文大學（非獨立法人）") == "香港中文大学"
    assert normalizer.school("香港中文大學（非獨立法人）") == normalizer.school("香港中文大學")


def test_aliases_are_normalized_before_lookup() -> None:
    normalizer = DefaultNormalizer(
        school_aliases={"Peking University": "北京大学"},
        member_aliases={"A-LICE": "Alice"},
    )
    assert normalizer.school("ＰＥＫＩＮＧ UNIVERSITY") == "北京大学"
    assert normalizer.member("a lice") == "alice"


def test_unicode_letters_outside_basic_cjk_are_preserved() -> None:
    normalizer = DefaultNormalizer()
    assert normalizer.member("龘𠮷") == "龘𠮷"


def test_empty_identity_is_rejected() -> None:
    with pytest.raises(DataValidationError, match="empty"):
        DefaultNormalizer().member("---")


def test_coach_suffixes() -> None:
    assert is_coach_name("张三（教练）")
    assert is_coach_name("Alice Coach")
    assert not is_coach_name("Coach Alice")
