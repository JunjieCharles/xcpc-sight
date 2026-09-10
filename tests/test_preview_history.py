import json

import pytest

from core import DefaultNormalizer
from scripts.preview_history import build_history_index, team_history


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
    assert all(r["medal"] is None for r in build_history_index(series, tmp_path, normalizer)[
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
