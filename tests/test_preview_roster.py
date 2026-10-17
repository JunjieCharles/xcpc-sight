from copy import deepcopy

import pytest

from core import DefaultNormalizer
from scripts.preview_roster import (
    ONLINE_CONTEST_IDS,
    attach_online_ranks,
    online_rank_index,
    parse_identity_roster,
    parse_roster_rows,
)

HEADERS = ["学校或单位", "中文队名", "类型", "队员1", "队员2", "队员3", "队伍 ID", "ICPC1"]


def test_reviewed_identity_roster_keeps_eligibility_and_ignores_scores():
    rows = [{"school": "学校", "name": "女队", "members": ["甲", "乙"],
             "excluded": False, "ratings": {"untrusted": 9999}},
            {"school": "学校", "name": "打星女队", "members": ["丙"], "excluded": True}]
    parsed = parse_identity_roster({"teams": rows})
    assert [t.excluded for t in parsed] == [False, True]
    assert parsed[0].members == ("甲", "乙")
    assert [t.source_index for t in parsed] == [0, 1]
    with pytest.raises(ValueError, match="duplicate team identity"):
        parse_identity_roster({"teams": [rows[0], rows[0]]})
    for key, value in [("excluded", None), ("excluded", "女队"), ("members", []),
                       ("members", ["甲", "甲"]), ("members", ["=BAD()"]),
                       ("school", None), ("members", [""])]:
        with pytest.raises(ValueError):
            parse_identity_roster({"teams": [{**rows[0], key: value}]})

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


@pytest.mark.parametrize("contest_id,count", [("icpc-2026-xian", 418),
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
        assert team.get("excluded", False) == identity["excluded"]
        assert [m["name"] for m in team["members"]] == identity["members"]
        for metric, index in indexes.items():
            values = []
            for member in team["members"]:
                match = index.match(member["name"], team["school"])
                assert member["ratings"][metric] == (match.rating if match else None)
                if match:
                    values.append(match.rating)
            assert team["ratings"][metric] == normalized_lse_rating(values)


def test_xian_manual_starred_teams_and_two_member_team():
    import json
    from pathlib import Path

    root = Path(__file__).parents[1]
    preview = json.loads((root / "static/data/previews/icpc-2026-xian.json").read_text("utf-8"))
    assert [team["name"] for team in preview["teams"] if team["excluded"]] == [
        "梦熊-PKU-1", "突然的陀螺", "梦熊信奥-D 类参赛", "动态仙人掌批发",
        "2026 感受内训 ACM 组队", "注意力大赛注意力战队", "海底小纵队", "不知道",
        "常常一等", "葫芦娃救爷爷", "没有赵哥的日子", "照输君", "信竞少女の廻天",
        "向着星辰与深渊", "西河谷底的发条公主",
    ]
    assert all(not team["excluded"] for team in preview["teams"][:403])
    assert all(team["excluded"] for team in preview["teams"][403:])
    assert [team["sourceIndex"] for team in preview["teams"]] == list(range(418))
    assert len({team["id"] for team in preview["teams"]}) == 418
    foshan = next(team for team in preview["teams"] if team["school"] == "佛山大学")
    assert [m["name"] for m in foshan["members"]] == ["刘骏学", "陈凯鹏"]
    assert preview["matchingSummary"]["members"] == 1253
    for metric in preview["metricSources"]:
        key = metric["id"]
        assert preview["matchingSummary"][key] == sum(
            member["ratings"][key] is not None
            for team in preview["teams"] for member in team["members"]
        )


def test_published_official_sources_match_reviewed_files():
    import hashlib
    import json
    from pathlib import Path

    static = Path(__file__).parents[1] / "static"
    xian = json.loads((static / "data/previews/icpc-2026-xian.json").read_text("utf-8"))
    roster = json.loads((static / "data/rosters/icpc-2026-xian.json").read_text("utf-8"))
    pdf = static / xian["teamSource"]["url"].removeprefix("./")
    assert pdf.suffix == ".pdf"
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == roster["sourceSha256"]
    changchun = json.loads((static / "data/previews/ccpc-2026-changchun.json").read_text("utf-8"))
    roster = json.loads((static / "data/rosters/ccpc-2026-changchun.json").read_text("utf-8"))
    pdf = static / changchun["teamSource"]["url"].removeprefix("./")
    assert pdf.name == "ccpc-2026-changchun-manual.pdf"
    assert changchun["teamSource"]["title"] == roster["source"]
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == roster["sourceSha256"] == (
        "386f3093f33ad88fe16d9f47d71f42815325e808cdf13dc4900312613f9d7497"
    )
    tianjin = next(t for t in roster["teams"] if t["school"] == "天津商业大学")
    assert tianjin["members"] == ["肖卫东", "魏泽鸣", "李洳帆"]
    assert sum(not t["excluded"] for t in roster["teams"]) == 300
    assert sum(len(t["members"]) for t in roster["teams"]) == 1007
    # Historical image sources remain available for existing links.
    gallery = static / "sources/ccpc-2026-changchun"
    html = (gallery / "index.html").read_text("utf-8")
    assert len(roster["statusSources"]) == html.count("<img ") == 10
    assert not list(gallery.glob("*.xlsx"))
    assert ".xlsx" not in html
    offsets = []
    for page in [7, 9, 4, 1, 6, 3, 5, 2, 8, 10]:
        source = roster["statusSources"][page - 1]
        digest = hashlib.sha256((gallery / source["file"]).read_bytes()).hexdigest()
        assert digest == source["sha256"]
        offsets.append(html.index(f'src="{source["file"]}"'))
    assert offsets == sorted(offsets)


def test_changchun_image_statuses_match_all_marked_teams():
    import json
    from pathlib import Path

    root = Path(__file__).parents[1]
    path = root / "static/data/previews/ccpc-2026-changchun.json"
    preview = json.loads(path.read_text("utf-8"))
    expected = {
        "该消息类型暂不支持查看", "兰德1队", "兰德2队", "兰德3队",
        "SET.部乐俱技竞子电搏滔", "被孤立的退役老哥和前途无量的学弟学妹", "运行时叛逆者",
        "德强", "平头弟", "平头哥", "哈理工202603CC", "征集雷霆队名",
        "主播我第一次打ccpc能不能赏我块牌啊", "天青色等烟雨", "帮我开下A103",
        "故障吉奇人", "卡卡", "没想好叫什么", "皮卡丘站起来是皮卡兵", "前有绝景",
        "时代码戏团", "我也要AC吗", "倚兰", "追忆", "区↺凶", "辽实东师附中联队",
        "我们常常追忆追忆", "网瘾战队", "掉进兔子洞", "默默不语", "贪得吴彦组",
        "云斗学院-星火燎原", "doro骑士团", "吃不完三菜一汤", "和光同尘", "正在启动",
    }
    assert {team["name"] for team in preview["teams"] if team["excluded"]} == expected
    female = next(team for team in preview["teams"] if team["name"] == "力拔山兮")
    assert female["school"] == "长春工业大学"
    assert not female["excluded"]
    hunan = next(team for team in preview["teams"] if team["school"] == "湖南农业大学")
    assert hunan["name"] == "零罚时"
    assert [m["name"] for m in hunan["members"]] == ["黄瑞莎", "周静", "颜诗祺"]
    assert not hunan["excluded"]


def test_static_generator_copies_xian_identity_source(tmp_path, monkeypatch):
    import json

    from scripts import generate_static_data

    monkeypatch.setattr(generate_static_data, "series_specs", lambda: ())
    monkeypatch.setattr(generate_static_data, "review_specs", lambda: ())
    generate_static_data.generate_static_data(tmp_path)
    roster = json.loads((tmp_path / "rosters/icpc-2026-xian.json").read_text("utf-8"))
    assert len(roster["teams"]) == 418
    assert (tmp_path / "previews/icpc-2026-xian.json").is_file()
    roster = json.loads((tmp_path / "rosters/ccpc-2026-changchun.json").read_text("utf-8"))
    assert len(roster["teams"]) == 336
    assert (tmp_path / "previews/ccpc-2026-changchun.json").is_file()
    summaries = json.loads((tmp_path / "regional-cutoffs/2026-2027.json").read_text("utf-8"))
    assert {c["id"] for c in summaries["contests"]} == {
        "icpc-2026-chengdu", "icpc-2026-wuhan",
    }
    index = json.loads((tmp_path / "index.json").read_text("utf-8"))
    entry = next(e for e in index["series"] if e["id"] == "2026-2027")
    assert entry["regionalCutoffsPath"] == "regional-cutoffs/2026-2027.json"
    assert not (tmp_path / "previews/icpc-2026-chengdu.json").exists()
    assert not (tmp_path / "previews/icpc-2026-wuhan.json").exists()
