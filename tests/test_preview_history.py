import json
from dataclasses import replace

import pytest

from core import DefaultNormalizer
from core.models import TeamResult
from scripts.preview_history import _history_medals, build_history_index, team_history


def medal_teams():
    return tuple(TeamResult(str(i), str(i), "school", (), i + 1,
                            20 - i if i < 10 else 0, 100 + i, has_activity=i < 10)
                 for i in range(20))


def resolve(options, teams=None):
    return _history_medals({"series": [{"rule": {"preset": "ICPC", "options": options}}],
                            "rows": []}, teams or medal_teams(), "test.srk.json")


@pytest.mark.parametrize("denominator,gold,silver,bronze", [
    ("all", 2, 6, 12), ("scored", 1, 3, 6), ("submitted", 0, 0, 0),
])
def test_ratio_cumulative_decimal_endpoints(denominator, gold, silver, bronze):
    teams = (*medal_teams(), replace(medal_teams()[0], team_id="guest", official=False))
    result = resolve({"ratio": {"value": [.1, .2, .3], "denominator": denominator}}, teams)
    assert "guest" not in result
    assert list(result.values()) == ["gold"] * gold + ["silver"] * (silver - gold) + [
        "bronze"] * (bronze - silver) + [None] * (20 - bronze)


@pytest.mark.parametrize("rounding,expected", [("ceil", 2), ("floor", 1), ("round", 2)])
def test_ratio_rounding(rounding, expected):
    result = resolve({"ratio": {"value": [.1, 0, 0], "rounding": rounding}}, medal_teams()[:15])
    assert list(result.values()).count("gold") == expected


@pytest.mark.parametrize("no_tied,expected", [(False, "gold"), (True, "silver")])
def test_medal_boundary_ties(no_tied, expected):
    teams = list(medal_teams())
    teams[1] = replace(teams[1], solved=teams[0].solved, penalty=teams[0].penalty)
    result = resolve({"ratio": {"value": [.05, .1, .15], "noTied": no_tied}}, teams)
    assert result["0"] == "gold"
    assert result["1"] == expected


def test_unknown_zero_counts_and_combined_rules():
    assert set(resolve({}).values()) == {None}
    assert set(resolve({"count": {"value": [0, 0, 0]}}).values()) == {None}
    result = resolve({"count": {"value": [1, 2, 3]}, "ratio": {"value": [.1, .2, .3]}})
    assert list(result.values())[:7] == [
        "gold", "silver", "silver", "bronze", "bronze", "bronze", None,
    ]


def test_submitted_denominator_uses_raw_statuses_and_excludes_guests():
    payload = {"series": [{"rule": {"preset": "ICPC", "options": {
        "ratio": {"value": [.5, 0, 0], "denominator": "submitted"}}}}],
        "rows": [{"user": {"id": uid}, "statuses": [{"result": result}]}
                 for uid, result in [("0", "AC"), ("1", "WA"), ("2", None), ("guest", "AC")]]}
    teams = (*medal_teams(), replace(medal_teams()[0], team_id="guest", official=False))
    medals = _history_medals(payload, teams, "submitted.srk.json")
    assert list(medals.values()).count("gold") == 1


def test_wuhan_cached_counts_repair_only_zero_placeholder():
    teams = tuple(replace(medal_teams()[0], team_id=str(i), penalty=i) for i in range(272))
    for counts in ([0, 0, 0], [45, 90, 136]):
        payload = {"series": [{"rule": {"preset": "ICPC", "options": {
            "count": {"value": counts}}}}], "rows": []}
        medals = _history_medals(payload, teams, "icpc2025wuhan.srk.json")
        assert list(medals.values()) == ["gold"] * 45 + ["silver"] * 90 + ["bronze"] * 136 + [None]


@pytest.mark.parametrize("options", [
    {"ratio": {"value": [True, .2, .3]}}, {"ratio": {"value": [float("nan"), .2, .3]}},
    {"ratio": {"value": [-.1, .2, .3]}}, {"ratio": {"value": [.5, .5, .5]}},
    {"ratio": {"value": [.1, .2]}}, {"ratio": {"value": [.1, .2, .3], "denominator": "bad"}},
    {"ratio": {"value": [.1, .2, .3], "rounding": "bad"}},
    {"count": {"value": [1, 2, 3], "noTied": "yes"}}, {"filter": {"byMarker": "x"}},
])
def test_invalid_medal_rules_have_file_context(options):
    with pytest.raises(ValueError, match="test.srk.json.*medal"):
        resolve(options)


def test_published_history_colors():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    expected = {"ccpc2025jinan": (3, "gold"), "ccpc2025zhengzhou": (18, "gold"),
                "icpc2025wuhan": (188, "bronze")}
    for filename in ("2026-2027.json", "icpc-2026-preliminary-2.json"):
        path = root / "static/data/previews" / filename
        document = json.loads(path.read_text(encoding="utf-8"))
        records = [r for t in document["teams"] for r in t["previousSeasonHistory"]
                   if r["teamName"] == "CQOI Flames"]
        for contest, (rank, medal) in expected.items():
            matched = [r for r in records if r["contestId"] == contest]
            assert matched
            assert all((r["rank"], r["medal"]) == (rank, medal) for r in matched)


def test_history_adapts_official_results_and_merges_members(tmp_path):
    def row(uid, name, members, solved, official=True, school="旧校名"):
        return {"user": {"id": uid, "name": name, "organization": school,
                         "teamMembers": [{"name": member} for member in members],
                         "official": official},
                "score": {"value": solved, "time": [100, "min"]}, "statuses": []}

    payload = {
        "contest": {"title": "区域赛", "startAt": "2025-10-01T09:00:00+08:00"},
        "series": [{"rule": {"preset": "ICPC", "options": {"count": {"value": [1, 1, 1]}}}}],
        "rows": [row("guest", "打星", ["甲"], 10, False),
                 row("a", "旧队名", ["甲", "乙", "乙"], 8),
                 row("b", "另一队", ["丙"], 7),
                 row("other", "同名异校", ["甲"], 6, school="另一大学"),
                 row("inactive", "无提交", ["甲"], 0)],
    }
    path = tmp_path / "icpc2025test.srk.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    series = {"contests": [{"id": "icpc2025test", "title": "区域赛", "collection": "icpc2025",
                            "startAt": "2025-10-01T09:00:00+08:00"}]}
    normalizer = DefaultNormalizer(school_aliases={"旧校名": "新校名"})
    index = build_history_index(series, tmp_path, normalizer)
    team = {"school": "新校名", "members": [{"name": n} for n in ["甲", "乙", "丙"]]}
    history = team_history(team, index, normalizer)
    assert [(r["teamName"], r["rank"], r["matchedMembers"], r["medal"]) for r in history] == [
        ("旧队名", 1, 2, "gold"), ("另一队", 2, 1, "silver"),
    ]
    team["members"].reverse()
    assert team_history(team, index, normalizer) == history
    team["members"] = [{"name": "新人"}]
    assert team_history(team, index, normalizer) == []
    payload["series"][0]["rule"]["options"] = {"ratio": {"value": [.1, .2, .3]}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert all(r["medal"] == "gold" for r in build_history_index(series, tmp_path, normalizer)[
        (normalizer.member("甲"), normalizer.school("新校名"))
    ])
    payload["series"][0]["rule"]["options"] = {"count": {"value": [-1, 2, 3]}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="icpc2025test.*medal counts"):
        build_history_index(series, tmp_path, normalizer)


def test_history_orders_icpc_before_ccpc_and_deduplicates_members():
    normalizer = DefaultNormalizer()
    def record(contest, date):
        return {"contestId": contest, "startAt": date, "teamId": "a", "rank": 1}
    first = record("icpc2025a", "2025-10-01")
    last = record("icpc2025b", "2025-11-01")
    ccpc = record("ccpc2025a", "2025-09-01")
    index = {(normalizer.member("甲"), normalizer.school("大学")): [last, ccpc, first, first]}
    team = {"school": "大学", "members": [{"name": "甲"}, {"name": "甲"}]}
    assert team_history(team, index, normalizer) == [
        {**r, "matchedMembers": 1} for r in [first, last, ccpc]
    ]


def test_missing_contest_reports_context(tmp_path):
    with pytest.raises(ValueError, match="missing history snapshot icpc2025missing"):
        build_history_index({"contests": [{"id": "icpc2025missing"}]}, tmp_path,
                            DefaultNormalizer())
