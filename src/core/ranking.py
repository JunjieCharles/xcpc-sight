from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from .errors import DataValidationError
from .models import TeamResult


def rebuild_competition_ranks(
    teams: Sequence[TeamResult],
    *,
    contest_id: str,
) -> tuple[TeamResult, ...]:
    """Rebuild active official team ranks from solved count and penalty."""
    eligible_scores: list[tuple[int, int]] = []
    for team in teams:
        if (
            isinstance(team.solved, bool)
            or not isinstance(team.solved, int)
            or team.solved < 0
        ):
            raise DataValidationError(
                f"contest {contest_id}, team {team.team_id}: solved must be non-negative"
            )
        if (
            isinstance(team.penalty, bool)
            or not isinstance(team.penalty, int)
            or team.penalty < 0
        ):
            raise DataValidationError(
                f"contest {contest_id}, team {team.team_id}: penalty must be non-negative"
            )
        if team.official and team.has_activity:
            eligible_scores.append((team.solved, team.penalty))

    score_counts = Counter(eligible_scores)
    ranks: dict[tuple[int, int], int] = {}
    position = 1
    for score in sorted(score_counts, key=lambda item: (-item[0], item[1])):
        ranks[score] = position
        position += score_counts[score]

    return tuple(
        replace(
            team,
            rank=(
                ranks[(team.solved, team.penalty)]
                if team.official and team.has_activity
                else 0
            ),
        )
        for team in teams
    )
