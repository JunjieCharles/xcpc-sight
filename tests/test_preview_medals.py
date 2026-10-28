import copy
import json
from pathlib import Path

import pytest

from core import DefaultNormalizer
from scripts.preview_medals import add_current_medals, supplement_medals


def fixture():
    member = {"name": "甲", "medals": {"gold": 2, "silver": 1, "bronze": 0}}
    preview = {"seriesId": "2026-2027", "sortAt": "2026-11-01T09:00:00+08:00",
               "sourceSnapshots": {"cpcfinder": "2026-10-10"},
               "teams": [{"school": "学校", "members": [member],
                          "medals": copy.deepcopy(member["medals"])}]}
    contests = [{"id": "icpc2026a", "startAt": "2026-10-18T09:00:00+08:00"},
                {"id": "icpc2026b", "startAt": "2026-10-25T09:00:00+08:00"},
                {"id": "same", "startAt": "2026-11-01T01:00:00Z"},
                {"id": "future", "startAt": "2026-11-08T09:00:00+08:00"},
                {"id": "icpc2026preliminary", "startAt": "2026-09-01T09:00:00+08:00"}]
    records = [{"contestId": c["id"], "rank": 1, "teamId": c["id"], "medal": "gold"}
               for c in contests]
    records[1]["medal"] = "silver"
    records.append({**records[0], "rank": 2, "teamId": "duplicate", "medal": "silver"})
    return preview, contests, {("甲", "学校"): records}


def test_member_counts_cutoff_identity_deduplication_and_idempotence():
    preview, contests, history = fixture()
    original = copy.deepcopy(preview)
    # A member absent from CPC Finder can still receive current-season medals.
    preview["teams"].append({"school": "学校", "excluded": True,
                             "members": [{"name": "甲", "medals": dict.fromkeys(
                                 ("gold", "silver", "bronze"), 0)}]})
    # Current roster eligibility does not erase official historical awards.
    result = supplement_medals(preview, contests, history, DefaultNormalizer())
    assert result["teams"][0]["medals"] == {"gold": 3, "silver": 2, "bronze": 0}
    assert result["teams"][1]["medals"] == {"gold": 1, "silver": 1, "bronze": 0}
    assert preview["teams"][0] == original["teams"][0]
    assert supplement_medals(result, contests, history, DefaultNormalizer()) == result
    # Re-running with corrected award bands replaces, rather than adds, medals.
    history[("甲", "学校")][0]["medal"] = "bronze"
    updated = supplement_medals(result, contests, history, DefaultNormalizer())
    assert updated["teams"][0]["medals"] == {"gold": 2, "silver": 2, "bronze": 1}
    other = copy.deepcopy(preview)
    other["teams"][0]["school"] = "另一校"
    other_result = supplement_medals(other, contests, history, DefaultNormalizer())
    assert other_result["teams"][0]["medals"] == original["teams"][0]["medals"]


def test_baseline_overlap_must_be_explicit_and_is_not_counted_twice():
    preview, contests, history = fixture()
    preview["sourceSnapshots"]["cpcfinder"] = "2026-10-19"
    with pytest.raises(ValueError, match="double counting"):
        supplement_medals(preview, contests, history, DefaultNormalizer())
    result = supplement_medals(preview, contests, history, DefaultNormalizer(), ["icpc2026a"])
    assert result["teams"][0]["medals"] == {"gold": 2, "silver": 2, "bronze": 0}
    assert supplement_medals(result, contests, history, DefaultNormalizer()) == result
    for ids in [["future"], ["icpc2026a", "icpc2026a"], ["icpc2026b"]]:
        with pytest.raises(ValueError):
            supplement_medals(preview, contests, history, DefaultNormalizer(), ids)
    result["sourceSnapshots"]["cpcfinder"] = "2026-10-26"
    with pytest.raises(ValueError, match="baseline changed"):
        supplement_medals(result, contests, history, DefaultNormalizer())


def test_unmatched_cpcfinder_member_still_gets_covered_contest_awards():
    preview, contests, history = fixture()
    preview["sourceSnapshots"]["cpcfinder"] = "2026-10-28"
    member = preview["teams"][0]["members"][0]
    member["ratings"] = {"cpcfinder": None}
    member["medals"] = {"gold": 0, "silver": 0, "bronze": 0}
    result = supplement_medals(preview, contests, history, DefaultNormalizer(),
                               ["icpc2026a", "icpc2026b"])
    assert result["teams"][0]["medals"] == {"gold": 1, "silver": 1, "bronze": 0}


def test_requires_real_current_results_and_valid_season(tmp_path):
    preview, contests, _ = fixture()
    series = {"id": "2026-2027", "contests": contests}
    with pytest.raises(ValueError, match="current-history-srk-root"):
        add_current_medals(preview, series, None, DefaultNormalizer())
    with pytest.raises(ValueError, match="missing history snapshot"):
        add_current_medals(preview, series, tmp_path, DefaultNormalizer())
    with pytest.raises(ValueError, match="match the preview season"):
        add_current_medals(preview, {**series, "id": "2025-2026"}, None, DefaultNormalizer())
    early = {**preview, "sortAt": "2026-09-06T13:00:00+08:00"}
    early["sourceSnapshots"] = {"cpcfinder": "2026-09-04"}
    assert add_current_medals(early, series, None, DefaultNormalizer()) == early


def test_srk_adapter_medal_rules_and_member_sum(tmp_path):
    from core import normalize_srk_contest
    from scripts.preview_history import _history_medals

    source = Path(__file__).parent / "fixtures/review/contest.srk.json"
    raw = json.loads(source.read_text("utf-8"))
    raw["series"] = [{"rule": {"preset": "ICPC", "options": {"count": {"value": [2, 2, 2]}}}}]
    (tmp_path / "icpc2026a.srk.json").write_text(json.dumps(raw), encoding="utf-8")
    contest = normalize_srk_contest(raw, contest_uk="icpc2026a", series="icpc2026")
    medals = _history_medals(raw, contest.teams, "icpc2026a.srk.json")
    teams = [{"school": t.school_name, "members": [
        {"name": name, "medals": {"gold": 0, "silver": 0, "bronze": 0}} for name in t.members
    ]} for t in contest.teams]
    preview, contests, _ = fixture()
    preview["teams"] = teams
    series = {"id": preview["seriesId"], "contests": [
        {**contests[0], "collection": "icpc2026", "title": "A"}]}
    result = add_current_medals(preview, series, tmp_path, DefaultNormalizer())
    for source, team in zip(contest.teams, result["teams"], strict=True):
        expected = medals.get(source.team_id) if source.official and source.has_activity else None
        assert team["medals"] == {m: len(source.members) if m == expected else 0
                                  for m in ("gold", "silver", "bronze")}


@pytest.mark.parametrize("name,expected,affected", [
    ("icpc-2026-chengdu", {"gold": 45, "silver": 61, "bronze": 77}, 183),
])
def test_published_medal_supplements_match_pre_contest_history(name, expected, affected):
    document = json.loads((Path(__file__).parents[1] / f"static/data/previews/{name}.json")
                          .read_text("utf-8"))
    members = [m for t in document["teams"] for m in t["members"]]
    assert {k: sum(m["medalSupplement"][k] for m in members) for k in expected} == expected
    assert sum(any(m["medalSupplement"].values()) for m in members) == affected
    for team in document["teams"]:
        assert team["medals"] == {k: sum(m["medals"][k] for m in team["members"])
                                  for k in expected}
        assert {k: sum(m["medalSupplement"][k] for m in team["members"]) for k in expected} == {
            k: sum(h["matchedMembers"] for h in team["currentSeasonHistory"] if h["medal"] == k)
            for k in expected}


def test_wuhan_latest_cpcfinder_already_covers_this_season_without_double_counting():
    path = Path(__file__).parents[1] / "static/data/previews/icpc-2026-wuhan.json"
    document = json.loads(path.read_text("utf-8"))
    assert document["snapshotDate"] == "2026-10-28"
    assert document["sourceSnapshots"]["xcpcrating"] == "2026-10-26T18:58:27.047236+00:00"
    assert document["sourceSnapshots"]["xcpcElo"] == "2026-10-25T09:41:47.011Z"
    assert document["sourceSnapshots"]["cpcfinder"] == document["sourcesFetchedAt"]
    assert document["medalSources"]["cpcfinderCoveredContestIds"] == [
        "ccpc2026changchun", "icpc2026chengdu", "icpc2026xi_an"]
    assert document["medalSources"]["addedContestIds"] == []
    members = [m for t in document["teams"] for m in t["members"]]
    assert not any(any(m["medalSupplement"].values()) for m in members)
    assert document["matchingSummary"]["cpcfinder"] == 761
    assert {k: sum(m["medals"][k] for m in members) for k in ("gold", "silver", "bronze")} == {
        "gold": 278, "silver": 518, "bronze": 777}
    for team in document["teams"]:
        for medal in ("gold", "silver", "bronze"):
            assert team["medals"][medal] == sum(m["medals"][medal] for m in team["members"])
            assert team["medals"][medal] >= sum(h["matchedMembers"]
                for h in team["currentSeasonHistory"] if h["medal"] == medal)
