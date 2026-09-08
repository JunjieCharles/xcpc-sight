from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import DefaultNormalizer
from scripts import generate_preview_data as generator
from scripts.generate_preview_data import (
    AchievementIndex,
    PersonIndex,
    PersonRecord,
    competition_ranks,
    parse_registered_team,
    stable_team_id,
)


def test_competition_ranks_preserve_ties_and_skip_following_places() -> None:
    assert competition_ranks([600, 580, 600, 550, 580]) == [1, 3, 1, 5, 3]


def test_achievement_matching_uses_only_name_and_orders_noi_before_ioi() -> None:
    records = [
        {"name": "张三", "competition": "ioi", "year": 2025, "medal": "silver"},
        {"name": "张三", "competition": "noi", "year": 2025, "medal": "gold"},
        {"name": "张三", "competition": "noi", "year": 2024, "medal": "bronze"},
    ]
    index = AchievementIndex(records)

    matched = index.match("张三")

    assert records[0]["name"] == "张三"
    assert [(item["year"], item["competition"]) for item in matched] == [
        (2024, "noi"),
        (2025, "noi"),
        (2025, "ioi"),
    ]
    matched[0]["medal"] = "gold"
    assert index.match("张三")[0]["medal"] == "bronze"
    assert index.match("李四") == []


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


@pytest.mark.parametrize("reverse", [False, True])
def test_cpcfinder_sums_normalized_identities_without_crossing_schools(reverse: bool) -> None:
    records = [
        PersonRecord("姜宣丞", "台湾大学", 10.10, (1, 2, 0)),
        PersonRecord("姜宣丞", "臺灣大學", 20.20, (2, 0, 3)),
        PersonRecord("姜宣丞", "另一大学", 999, (9, 9, 9)),
        PersonRecord("陳銘", "臺灣大學", 0, (0, 0, 0)),
        PersonRecord("陈铭", "台湾大学", 1.23, (0, 1, 0)),
    ]
    index = PersonIndex(
        records[::-1] if reverse else records, DefaultNormalizer(), sum_matches=True,
    )
    assert index.match("姜宣丞", "台湾大学") == PersonRecord(
        "姜宣丞", "台湾大学", 30.30, (3, 2, 3),
    )
    assert index.match("陳銘", "臺灣大學") == PersonRecord(
        "陈铭", "台湾大学", 1.23, (0, 1, 0),
    )
    assert index.match("姜宣丞", "未知大学") is None
    assert index.match("未知", "台湾大学") is None


def test_cpcfinder_merges_school_renames_aliases_and_punctuation(tmp_path: Path) -> None:
    normalizer = generator.load_normalizer(
        Path(__file__).resolve().parents[1] / "config/school-aliases.json"
    )
    schools = [
        "北京师范大学-香港浸会大学联合国际学院",
        "“北京师范大学香港浸会大学联合国际学院”",
        "北师香港浸会大学",
        "Beijing Normal-Hong Kong Baptist University",
        "北京師範大學香港浸會大學聯合國際學院",
    ]
    for page, school in enumerate(schools, start=1):
        (tmp_path / f"{page}.json").write_text(json.dumps({"data": [{
            "name": "陳銘" if page % 2 else "陈铭", "schoolName": school,
            "rating": "10.10", "goldCount": 1, "silverCount": 2, "bronzeCount": 3,
        }]}), encoding="utf-8")
    index = PersonIndex(generator.load_cpcfinder(tmp_path), normalizer, sum_matches=True)
    for school in schools:
        matched = index.match("陈铭", school)
        assert matched is not None
        assert matched.rating == 50.50
        assert matched.medals == (5, 10, 15)
    assert index.match("陈铭", "香港浸会大学") is None


@pytest.mark.parametrize("row", [[], ["队名", "English", "学校", ""]])
def test_registration_parser_rejects_incomplete_rows(row: list[str]) -> None:
    with pytest.raises(ValueError, match="team row 3"):
        parse_registered_team(row, 3)


def test_stable_team_id_uses_school_team_and_member_order() -> None:
    identity = stable_team_id("测试大学", "队名", ["甲", "乙", "丙"])

    assert identity == stable_team_id("测试大学", "队名", ["甲", "乙", "丙"])
    assert identity != stable_team_id("测试大学", "队名", ["甲", "丙", "乙"])


@pytest.mark.parametrize("with_current", [False, True])
def test_second_preview_metadata_and_cached_source_date(
    monkeypatch, tmp_path: Path, with_current: bool,
) -> None:
    teams = tmp_path / "teams.json"
    teams.write_text(json.dumps([["队名", "Team", "学校", "甲 / 乙", "教练"]]))
    monkeypatch.setattr("sys.argv", [
        "generate_preview_data", "--teams", str(teams),
        "--xcpcrating-data", ".", "--xcpc-elo-data", ".",
        "--previous-series", ".", "--cpcfinder-pages", ".",
        "--snapshot-date", "2026-09-07", "--cpcfinder-snapshot-date", "2026-09-04",
        "--preview-id", "icpc-2026-preliminary-2", "--preview-title", "第二场",
        "--team-source-url", "https://example.test/second", "--sort-at",
        "2026-09-12T13:00:00+08:00",
    ])
    monkeypatch.setattr(generator, "load_normalizer", lambda _: DefaultNormalizer())
    for name in ("load_xcpcrating", "load_xcpc_elo", "load_previous_series"):
        monkeypatch.setattr(generator, name, lambda _: ([], "2026-09-04"))
    monkeypatch.setattr(generator, "load_cpcfinder", lambda _: [
        PersonRecord("甲", "学校", 10.10, (1, 0, 2)),
        PersonRecord("甲", "學校", 20.20, (0, 3, 1)),
        PersonRecord("乙", "学校", 25, (2, 1, 0)),
    ])
    monkeypatch.setattr(generator, "load_achievements", lambda *_: AchievementIndex([]))

    args = generator.parse_args()
    assert args.school_aliases == Path(generator.__file__).resolve().parents[1] / (
        "config/school-aliases.json"
    )
    if with_current:
        current = tmp_path / "current.json"
        current.write_text(json.dumps({"id": "2026-2027"}))
        args.current_series = current
        monkeypatch.setattr(generator, "load_previous_series", lambda path: (
            [PersonRecord("甲", "学校", 1600), PersonRecord("乙", "另一学校", 1700)]
            if path == current else [], "2026-09-06T13:00:00+08:00",
        ))
    document = generator.build_document(args)

    assert document["id"] == "icpc-2026-preliminary-2"
    assert document["title"] == "第二场"
    assert document["sortAt"] == "2026-09-12T13:00:00+08:00"
    assert document["teamSource"]["url"] == "https://example.test/second"
    assert document["snapshotDate"] == "2026-09-07"
    assert document["sourceSnapshots"]["cpcfinder"] == "2026-09-04"
    assert document["matchingSummary"]["members"] == 2
    assert document["matchingSummary"]["cpcfinder"] == 2
    assert document["teams"][0]["members"][0]["ratings"]["cpcfinder"] == 30.30
    assert document["teams"][0]["members"][0]["medals"] == {
        "gold": 1, "silver": 3, "bronze": 3,
    }
    assert document["teams"][0]["ratings"]["cpcfinder"] == 30.30
    assert document["teams"][0]["medals"] == {"gold": 3, "silver": 4, "bronze": 3}
    assert [m["name"] for m in document["teams"][0]["members"]] == ["甲", "乙"]
    if with_current:
        assert [s["id"] for s in document["metricSources"]] == [
            "xcpcrating", "xcpcElo", "previousSeason", "currentSeason", "cpcfinder",
        ]
        assert document["sourceSnapshots"]["currentSeason"] == "2026-09-06T13:00:00+08:00"
        assert document["teams"][0]["ratings"]["currentSeason"] == 1600
        assert document["teams"][0]["members"][1]["ratings"]["currentSeason"] is None
        assert document["matchingSummary"]["currentSeason"] == 1
        args.sort_at = "2026-09-06T13:00:00+08:00"
        with pytest.raises(ValueError, match="must precede"):
            generator.build_document(args)
        current.write_text(json.dumps({"id": "2025-2026"}))
        with pytest.raises(ValueError, match="expected series"):
            generator.build_document(args)
    else:
        assert "currentSeason" not in document["teams"][0]["ratings"]


def test_default_publication_includes_both_preview_snapshots() -> None:
    from scripts.generate_static_data import preview_specs

    documents = [json.loads(spec.source.read_text(encoding="utf-8")) for spec in preview_specs()]
    assert [document["id"] for document in documents] == [
        "icpc-2026-preliminary-1", "icpc-2026-preliminary-2",
    ]
    assert [len(document["teams"]) for document in documents] == [2535, 2636]
    for document in documents:
        matches = [
            member for team in document["teams"] for member in team["members"]
            if member["name"] == "姜宣丞" and team["school"] == "香港中文大学"
        ]
        assert len(matches) == 1
        assert matches[0]["ratings"]["cpcfinder"] == 1880.17
        assert matches[0]["medals"] == {"gold": 5, "silver": 3, "bronze": 1}
