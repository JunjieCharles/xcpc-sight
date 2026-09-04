from __future__ import annotations

import pytest

from core import DefaultNormalizer
from scripts.generate_preview_data import (
    PersonIndex,
    PersonRecord,
    parse_registered_team,
    stable_team_id,
)


def test_person_matching_uses_name_first_and_requires_matching_school() -> None:
    normalizer = DefaultNormalizer(
        school_aliases={"测试大学（主校区）": "测试大学"}
    )
    index = PersonIndex(
        [
            PersonRecord("张三", "测试大学", 1800),
            PersonRecord("张三", "另一大学", 2200),
            PersonRecord("张三", "测试大学", 1900),
        ],
        normalizer,
    )

    matched = index.match("张 三", "测试大学（主校区）")

    assert matched is not None
    assert matched.rating == 1900
    assert index.match("张三", "未知大学") is None
    assert index.match("李四", "测试大学") is None


def test_registration_parser_excludes_coach_columns() -> None:
    team = parse_registered_team(
        ["中文队名", "English name", "测试大学", "甲 / 乙/丙", "教练甲 / 教练乙"],
        7,
    )

    assert team.source_index == 7
    assert team.name == "中文队名"
    assert team.school == "测试大学"
    assert team.members == ("甲", "乙", "丙")
    assert "教练甲" not in team.members


@pytest.mark.parametrize("row", [[], ["队名", "English", "学校", ""]])
def test_registration_parser_rejects_incomplete_rows(row: list[str]) -> None:
    with pytest.raises(ValueError, match="team row 3"):
        parse_registered_team(row, 3)


def test_stable_team_id_uses_school_team_and_member_order() -> None:
    identity = stable_team_id("测试大学", "队名", ["甲", "乙", "丙"])

    assert identity == stable_team_id("测试大学", "队名", ["甲", "乙", "丙"])
    assert identity != stable_team_id("测试大学", "队名", ["甲", "丙", "乙"])
