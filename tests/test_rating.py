from datetime import datetime

import pytest

from core import (
    CompetitorId,
    Contest,
    DataValidationError,
    IdentityConflictError,
    TeamResult,
)
from rating import (
    RatingConfig,
    calculate_contest_ratings,
    calculate_series_ratings,
)


def contest(*teams: TeamResult, contest_id: str = "c1") -> Contest:
    return Contest(contest_id, contest_id, "icpc2025", datetime(2025, 9, 1), teams)


def team(
    team_id: str,
    rank: int,
    members: tuple[str, ...],
    *,
    school: str = "大学",
    official: bool = True,
    activity: bool = True,
    solved: int = 1,
    penalty: int | None = None,
) -> TeamResult:
    return TeamResult(
        team_id,
        team_id,
        school,
        members,
        rank,
        solved,
        rank * 1_000 if penalty is None else penalty,
        official,
        activity,
    )


def test_empty_contest_preserves_input_without_mutating_it() -> None:
    person = CompetitorId("大学", "甲")
    initial = {person: 1500}
    result = calculate_contest_ratings(contest(), initial)
    assert result.changes == ()
    assert dict(result.ratings) == initial
    assert initial == {person: 1500}


def test_corrected_rating_golden_vector_and_top_correction() -> None:
    result = calculate_contest_ratings(
        contest(
            team("one", 1, ("甲",)),
            team("two", 2, ("乙",)),
            team("three", 3, ("丙",)),
            team("four", 4, ("丁",)),
        )
    )
    changes = {change.display_member: change for change in result.changes}
    assert {name: change.new_rating for name, change in changes.items()} == {
        "甲": 1512,
        "乙": 1419,
        "丙": 1361,
        "丁": 1307,
    }
    assert {change.global_correction for change in result.changes} == {-11}
    assert {change.top_correction for change in result.changes} == {0}


def test_top_correction_is_applied_to_all_competitors() -> None:
    normalizer_ratings = {
        CompetitorId("u", f"p{i}"): 3000 - i * 50 for i in range(1, 26)
    }
    result = calculate_contest_ratings(
        contest(
            *(
                team(str(i), i, (f"p{i}",), school="u")
                for i in range(1, 26)
            )
        ),
        normalizer_ratings,
    )
    assert {change.top_correction for change in result.changes} == {-9}


def test_top_correction_can_be_disabled_explicitly() -> None:
    configured = calculate_contest_ratings(
        contest(team("one", 1, ("甲",)), team("two", 2, ("乙",))),
        config=RatingConfig(apply_top_correction=False),
    )
    assert {change.top_correction for change in configured.changes} == {0}


def test_unofficial_and_no_activity_teams_are_not_rated() -> None:
    result = calculate_contest_ratings(
        contest(
            team("official", 1, ("甲",)),
            team("unofficial", 0, ("乙",), official=False),
            team("inactive", 2, ("丙",), activity=False),
        )
    )
    assert [change.display_member for change in result.changes] == ["甲"]


def test_ranks_are_rebuilt_from_active_official_scores_with_ties() -> None:
    result = calculate_contest_ratings(
        contest(
            team("winner", 91, ("甲",), solved=2, penalty=10_000),
            team("inactive", 1, ("乙",), activity=False, solved=2, penalty=20_000),
            team("tie-a", 92, ("丙",), solved=1, penalty=30_000),
            team("tie-b", 93, ("丁",), solved=1, penalty=30_000),
            team("last", 94, ("戊",), solved=0, penalty=40_000),
        )
    )
    ranks = {change.display_member: change.rank for change in result.changes}
    assert ranks == {"甲": 1, "丙": 2, "丁": 2, "戊": 4}


@pytest.mark.parametrize(("field", "value"), [("solved", -1), ("penalty", -1)])
def test_rank_rebuild_rejects_invalid_scores(field: str, value: int) -> None:
    values = {"solved": 1, "penalty": 1_000}
    values[field] = value
    with pytest.raises(DataValidationError, match=field):
        calculate_contest_ratings(
            contest(team("invalid", 1, ("甲",), **values))
        )


def test_duplicate_identity_defaults_to_best_rank() -> None:
    result = calculate_contest_ratings(
        contest(team("one", 1, ("甲",)), team("two", 2, ("甲",)))
    )
    assert len(result.changes) == 1
    assert result.changes[0].rank == 1


def test_duplicate_identity_in_two_teams_can_be_rejected() -> None:
    with pytest.raises(IdentityConflictError, match="multiple teams"):
        calculate_contest_ratings(
            contest(team("one", 1, ("甲",)), team("two", 2, ("甲",))),
            config=RatingConfig(duplicate_competitor="error"),
        )


def test_explicit_rating_entity_uses_stable_identity_and_display_values() -> None:
    competitor = CompetitorId("nowcoder", "standing:42")
    explicit = TeamResult(
        "42",
        "旧队名",
        "旧学校",
        (),
        1,
        1,
        10,
        rating_competitor=competitor,
        rating_display_school="展示学校",
        rating_display_member="展示队名",
    )
    result = calculate_contest_ratings(contest(explicit))
    assert result.changes[0].competitor == competitor
    assert result.changes[0].display_school == "展示学校"
    assert result.changes[0].display_member == "展示队名"


def test_explicit_rating_entity_preserves_duplicate_validation() -> None:
    competitor = CompetitorId("nowcoder", "standing:42")
    teams = tuple(
        TeamResult(
            str(index),
            str(index),
            "学校",
            (),
            index,
            1,
            10,
            rating_competitor=competitor,
            rating_display_school="学校",
            rating_display_member=f"队伍{index}",
        )
        for index in (1, 2)
    )
    with pytest.raises(IdentityConflictError, match="multiple teams"):
        calculate_contest_ratings(
            contest(*teams), config=RatingConfig(duplicate_competitor="error")
        )


def test_series_uses_previous_contest_rating() -> None:
    first = contest(team("one", 1, ("甲",)), contest_id="first")
    second = contest(
        team("two", 1, ("乙",)),
        team("one", 2, ("甲",)),
        contest_id="second",
    )
    result = calculate_series_ratings((first, second))
    first_rating = result.contests[0].changes[0].new_rating
    second_change = next(
        change for change in result.contests[1].changes if change.display_member == "甲"
    )
    assert second_change.old_rating == first_rating


def test_unrated_contest_records_ranks_without_changing_ratings() -> None:
    existing = CompetitorId("大学", "甲")
    unrated = Contest(
        "unrated",
        "故障场",
        "series",
        datetime(2025, 9, 2),
        (
            team("new", 99, ("乙",), solved=2, penalty=20_000),
            team("existing", 98, ("甲",), solved=3, penalty=10_000),
        ),
        unrated_reason="checker挂了",
    )

    result = calculate_contest_ratings(unrated, {existing: 1729})
    changes = {change.display_member: change for change in result.changes}

    assert changes["甲"].rank == 1
    assert changes["甲"].old_rating == changes["甲"].new_rating == 1729
    assert changes["乙"].rank == 2
    assert changes["乙"].old_rating == changes["乙"].new_rating == 1400
    assert {change.delta for change in result.changes} == {0}
    assert dict(result.ratings) == {
        existing: 1729,
        CompetitorId("大学", "乙"): 1400,
    }


def test_unrated_contest_requires_a_nonempty_reason() -> None:
    invalid = Contest(
        "unrated",
        "故障场",
        "series",
        datetime(2025, 9, 2),
        (team("one", 1, ("甲",)),),
        unrated_reason=" ",
    )

    with pytest.raises(DataValidationError, match="reason must not be empty"):
        calculate_contest_ratings(invalid)
