import json

from problem_rating.predict_xcpc import (
    load_rankland_contest,
    max_member_rating,
    parse_hdu_accepted_time,
    stable_competitor_id,
    stable_member_competitor_id,
)


def test_parse_hdu_accepted_time_ignores_failed_only_cells():
    assert parse_hdu_accepted_time("00:03:07") == 187
    assert parse_hdu_accepted_time("02:24:26 (-3)") == 8666
    assert parse_hdu_accepted_time("(-14)") is None
    assert parse_hdu_accepted_time("") is None


def test_stable_competitor_id_keeps_sources_separate():
    nowcoder = stable_competitor_id("nowcoder", "standing:123")
    hdu = stable_competitor_id("hdu", "standing:123")

    assert nowcoder.startswith("c_")
    assert len(nowcoder) == 66
    assert hdu != nowcoder


def test_rankland_team_rating_is_maximum_of_every_member_rating():
    alice = stable_member_competitor_id("Example University", "Alice")
    bob = stable_member_competitor_id("Example University", "Bob")
    ratings = {alice: 1700, bob: 1930}

    assert max_member_rating("Example University", ["Alice", "Bob"], ratings) == 1930
    assert max_member_rating("Example University", ["Alice", "Missing"], ratings) is None


def test_load_rankland_contest_adapts_problem_results_with_max_member_rating(tmp_path):
    contest_id = "regional"
    cache_dir = tmp_path / "rankland"
    cache_dir.mkdir()
    srk = {
        "contest": {
            "title": "Regional",
            "startAt": "2025-10-01T09:00:00+08:00",
            "duration": [5, "h"],
        },
        "problems": [{"alias": "A"}, {"alias": "B"}],
        "rows": [
            {
                "rank": 1,
                "user": {
                    "id": "team-1",
                    "name": "Team One",
                    "organization": "Example University",
                    "official": True,
                    "teamMembers": [
                        {"name": "Alice"},
                        {"name": "Bob"},
                        {"name": "Advisor", "role": "coach"},
                    ],
                },
                "score": {"value": 1, "time": [100, "min"]},
                "statuses": [
                    {"result": "AC", "tries": 1, "time": [100, "s"]},
                    {"result": "WA", "tries": 2},
                ],
            }
        ],
    }
    (cache_dir / "rankland-regional.json").write_text(
        json.dumps({"contestId": contest_id, "srk": srk}),
        encoding="utf-8",
    )
    ratings = {
        stable_member_competitor_id("Example University", "Alice"): 1700,
        stable_member_competitor_id("Example University", "Bob"): 1930,
    }

    loaded = load_rankland_contest(
        {
            "id": contest_id,
            "title": "Regional",
            "startAt": "2025-10-01T09:00:00+08:00",
        },
        ratings,
        cache_dir,
    )

    assert loaded.series == "2025-2026"
    assert loaded.duration_seconds == 18_000
    assert loaded.problems[0][1] == "RankLand 公开榜单未提供题名"
    assert loaded.participants[0].rating == 1930
    assert loaded.participants[0].accepted_times == {"A": 100}
