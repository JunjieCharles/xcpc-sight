from copy import deepcopy

import pytest

from core import DefaultNormalizer
from scripts.preview_roster import (
    ONLINE_CONTEST_IDS,
    attach_online_ranks,
    online_rank_index,
    parse_roster_rows,
)

HEADERS = ["学校或单位", "中文队名", "类型", "队员1", "队员2", "队员3", "队伍 ID", "ICPC1"]

CCPC_HEADERS = ["序号", "所属学校", "中文队名", "队员1姓名", "队员2姓名", "队员3姓名", "教练姓名"]


def test_ccpc_roster_ignores_coach_and_preserves_identities():
    row = [1, "学校", "队伍", "张三", "李四", "王五", "=PRIVATE()"]
    teams = parse_roster_rows([["标题"], CCPC_HEADERS, row])
    assert len(teams) == 1
    assert teams[0].members == ("张三", "李四", "王五")
    assert teams[0].school == "学校"
    assert teams[0].name == "队伍"
    assert teams[0].source_index == 0
    assert not teams[0].excluded
    with pytest.raises(ValueError, match="row 4: duplicate team ID"):
        parse_roster_rows([["标题"], CCPC_HEADERS, row, row])


@pytest.mark.parametrize("column,value", [(0, None), (0, True), (0, 0), (1, None),
                                          (3, "=BAD()"), (4, "张三")])
def test_ccpc_roster_rejects_invalid_identity_with_source_row(column, value):
    row = [1, "学校", "队伍", "张三", "李四", "王五", "教练"]
    row[column] = value
    with pytest.raises(ValueError, match="roster row 4"):
        parse_roster_rows([["标题"], CCPC_HEADERS, [None], row])


def test_roster_uses_only_identities_and_preserves_order():
    rows = [["title"], HEADERS, ["学校", "队伍", "正式", "张三", "李四", None, "id", "=1/0"]]
    teams = parse_roster_rows(rows)
    assert teams[0].members == ("张三", "李四")
    assert teams[0].source_index == 0
    assert not teams[0].excluded
    changed = deepcopy(rows)
    changed[2][-1] = 9999
    assert parse_roster_rows(changed) == teams
    changed[2][2] = "打星"
    assert parse_roster_rows(changed)[0].excluded


@pytest.mark.parametrize("column,value", [(0, None), (2, "未知"), (3, "=BAD()"), (6, None)])
def test_roster_reports_bad_identity_with_row(column, value):
    row = ["学校", "队伍", "正式", "张三", None, None, "id", 1]
    row[column] = value
    with pytest.raises(ValueError, match="roster row 2"):
        parse_roster_rows([HEADERS, row])


def test_roster_rejects_duplicate_ids_and_missing_header():
    row = ["学校", "队伍", "正式", "张三", None, None, "id", 1]
    with pytest.raises(ValueError, match="duplicate team ID"):
        parse_roster_rows([HEADERS, row, row])
    with pytest.raises(ValueError, match="missing identity headers"):
        parse_roster_rows([["unrelated"]])


def sample_series():
    return {
        "contests": [{"id": id, "startAt": "2026-09-19T13:00:00+08:00"}
                     for id in ONLINE_CONTEST_IDS],
        "competitors": [
            {"school": school, "member": name, "participations": [
                {"contestIndex": i, "contestRank": rank} for i, rank in enumerate(ranks)
                if rank is not None
            ]}
            for school, name, ranks in [
                ("学校", "张三", [10, 40, None]), ("旧校名", "张三", [12, 30, 9]),
                ("学校", "李四", [20, 5, None]), ("另一学校", "张三", [1, 1, 1]),
            ]
        ],
    }


def test_online_matching_alias_reorganization_missing_and_order():
    normalizer = DefaultNormalizer(school_aliases={"旧校名": "学校"})
    series = sample_series()
    index = online_rank_index(series, normalizer, "2026-10-18T00:00:00+08:00")
    teams = [{"school": "学校", "members": [{"name": name}]
              } for name in ["张三", "新队员"]]
    teams.append({"school": "学校", "members": [{"name": "张三"}, {"name": "李四"}]})
    attach_online_ranks(teams, index, normalizer)
    assert teams[0]["onlineRanks"] == [10, 30, 9]
    assert teams[1]["onlineRanks"] == [None, None, None]
    assert teams[2]["onlineRanks"] == [10, 5, 9]
    series["competitors"].reverse()
    assert online_rank_index(series, normalizer, "2026-10-18T00:00:00+08:00") == index


def test_online_sources_require_all_three_past_contests_and_positive_ranks():
    series = sample_series()
    with pytest.raises(ValueError, match="precede"):
        online_rank_index(series, DefaultNormalizer(), "2026-09-19T13:00:00+08:00")
    series["competitors"][0]["participations"][0]["contestRank"] = 0
    with pytest.raises(ValueError, match="invalid rank"):
        online_rank_index(series, DefaultNormalizer(), "2026-10-18T00:00:00+08:00")
    series["contests"].pop()
    with pytest.raises(ValueError, match="expected both"):
        online_rank_index(series, DefaultNormalizer(), "2026-10-18T00:00:00+08:00")


@pytest.mark.parametrize("contest_id,count", [("icpc-2026-xian", 403),
                                             ("ccpc-2026-changchun", 336)])
def test_published_regional_ranks_and_ratings_match_local_series(contest_id, count):
    import json
    from pathlib import Path

    from rating import normalized_lse_rating
    from scripts.generate_preview_data import PersonIndex, load_normalizer, load_previous_series

    root = Path(__file__).parents[1]
    preview = json.loads((root / f"static/data/previews/{contest_id}.json").read_text("utf-8"))
    roster = json.loads((root / f"static/data/rosters/{contest_id}.json").read_text("utf-8"))
    normalizer = load_normalizer(root / "config/school-aliases.json")
    series = json.loads((root / "static/data/series/2026-2027.json").read_text("utf-8"))
    indexes = {
        metric: PersonIndex(load_previous_series(root / f"static/data/series/{year}.json")[0],
                            normalizer)
        for metric, year in [("currentSeason", "2026-2027"), ("previousSeason", "2025-2026")]
    }
    ranks = online_rank_index(series, normalizer, preview["sortAt"])
    projected = deepcopy(preview["teams"])
    attach_online_ranks(projected, ranks, normalizer)
    assert projected == preview["teams"]
    assert len(roster["teams"]) == len(projected) == count
    for team, identity in zip(projected, roster["teams"], strict=True):
        assert team["school"] == identity["school"]
        assert team["name"] == identity["name"]
        assert [m["name"] for m in team["members"]] == identity["members"]
        for metric, index in indexes.items():
            values = []
            for member in team["members"]:
                match = index.match(member["name"], team["school"])
                assert member["ratings"][metric] == (match.rating if match else None)
                if match:
                    values.append(match.rating)
            assert team["ratings"][metric] == normalized_lse_rating(values)


def test_static_generator_copies_xian_identity_source(tmp_path, monkeypatch):
    import json

    from scripts import generate_static_data

    monkeypatch.setattr(generate_static_data, "series_specs", lambda: ())
    monkeypatch.setattr(generate_static_data, "review_specs", lambda: ())
    generate_static_data.generate_static_data(tmp_path)
    roster = json.loads((tmp_path / "rosters/icpc-2026-xian.json").read_text("utf-8"))
    assert len(roster["teams"]) == 403
    assert (tmp_path / "previews/icpc-2026-xian.json").is_file()
    roster = json.loads((tmp_path / "rosters/ccpc-2026-changchun.json").read_text("utf-8"))
    assert len(roster["teams"]) == 336
    assert (tmp_path / "previews/ccpc-2026-changchun.json").is_file()
