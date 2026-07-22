from datetime import datetime

from core import Contest, TeamResult, select_season
from rating import calculate_series_ratings


def make_contest(contest_id: str, series: str, day: int, members: tuple[str, ...]) -> Contest:
    teams = (
        TeamResult("one", "One", "大学", members, 1, 1, 10, True, True),
        TeamResult("two", "Two", "另一大学", ("乙",), 2, 1, 20, True, True),
    )
    return Contest(contest_id, contest_id, series, datetime(2025, 10, day, 9), teams)


def test_season_selection_and_series_rating_end_to_end() -> None:
    icpc = make_contest("icpc-regional", "icpc2025", 1, ("甲",))
    ccpc = make_contest("ccpc-regional", "ccpc2025", 1, ("丙",))
    invitation = make_contest("invite", "icpc2025", 2, ("丁",))
    invitation = Contest(
        invitation.contest_id,
        "ICPC Invitational",
        invitation.series,
        invitation.start_at,
        invitation.teams,
    )
    season = select_season((icpc, invitation, ccpc))
    assert [contest.contest_id for contest in season.contests] == [
        "ccpc-regional",
        "icpc-regional",
    ]
    result = calculate_series_ratings(season.contests)
    assert len(result.contests) == 2
    assert len(result.ratings) == 3
    returning = next(
        change
        for change in result.contests[1].changes
        if change.display_member == "乙"
    )
    assert returning.old_rating != 1400
