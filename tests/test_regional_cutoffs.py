import copy
import json
from pathlib import Path

from core import DefaultNormalizer
from scripts.generate_preview_data import RegisteredTeam
from scripts.generate_regional_cutoffs import build_summary, calculate_cutoffs
from scripts.preview_roster import ONLINE_CONTEST_IDS


def test_cutoffs_official_quotas_school_third_missing_and_input_unchanged():
    teams = [{"school": "same" if i < 2 else str(i), "onlineRanks": [100, i + 1, None]}
             for i in range(11)]
    teams.append({"school": "star", "onlineRanks": [1, 1, 1], "excluded": True})
    before = copy.deepcopy(teams)
    assert calculate_cutoffs(teams)[0] == {"cup": 4, "gold": 2, "silver": 5, "bronze": 9}
    assert teams == before
    assert calculate_cutoffs([])[0] == dict.fromkeys(["cup", "gold", "silver", "bronze"])
    assert calculate_cutoffs([{"school": "a", "onlineRanks": [None] * 3}])[0] == (
        calculate_cutoffs([])[0]
    )


def test_summary_matches_aliases_reorganized_members_and_ignores_stars():
    series = {
        "contests": [{"id": id, "startAt": "2026-09-19T00:00:00+08:00"}
                     for id in ONLINE_CONTEST_IDS],
        "competitors": [
            {"school": "A", "member": "one", "participations": [
                {"contestIndex": 0, "contestRank": 20}]},
            {"school": "A", "member": "two", "participations": [
                {"contestIndex": 1, "contestRank": 3}]},
        ],
    }
    registered = [RegisteredTeam(0, "team", "Alias", ("one", "two", "missing"), False),
                  RegisteredTeam(1, "star", "A", ("two",), True)]
    summary, audit = build_summary(
        registered, series, DefaultNormalizer(school_aliases={"Alias": "A"}),
        contest_id="icpc-test", title="test", sort_at="2026-10-25T09:00:00+08:00",
        host_school="host",
    )
    assert summary["officialTeamCount"] == summary["excludedTeamCount"] == 1
    assert summary["matchedOfficialTeamCount"] == 1
    assert summary["cutoffs"] == {"cup": None, "gold": 3, "silver": None, "bronze": None}
    assert audit["teams"][0]["onlineRanks"] == [20, 3, None]
    assert "teams" not in summary


def test_python_cutoffs_match_existing_published_preview_results():
    root = Path(__file__).resolve().parents[1] / "static/data/previews"
    for name, expected in [("icpc-2026-xian", [11, 117, 288, 658]),
                           ("ccpc-2026-changchun", [10, 84, 252, 576])]:
        teams = json.loads((root / f"{name}.json").read_text(encoding="utf-8"))["teams"]
        assert list(calculate_cutoffs(teams)[0].values()) == expected
