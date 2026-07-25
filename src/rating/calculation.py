from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from core.errors import DataValidationError, IdentityConflictError
from core.models import CompetitorId, Contest
from core.normalization import DefaultNormalizer, is_coach_name

from .models import (
    CompetitorRatingChange,
    ContestRatingResult,
    RatingConfig,
    SeriesRatingResult,
)


def _trunc_div(dividend: int, divisor: int) -> int:
    if divisor == 0:
        raise ZeroDivisionError("division by zero")
    sign = -1 if (dividend < 0) != (divisor < 0) else 1
    return sign * (abs(dividend) // abs(divisor))


def _seed(
    rating_counts: Mapping[int, int],
    candidate_rating: int,
    scale: int,
    own_rating: int | None = None,
) -> float:
    own_rating = candidate_rating if own_rating is None else own_rating
    seed = 1.0
    for rating, count in rating_counts.items():
        seed += count / (1.0 + 10 ** ((candidate_rating - rating) / scale))
    seed -= 1.0 / (1.0 + 10 ** ((candidate_rating - own_rating) / scale))
    return seed


def _performance_rating(
    rating_counts: Mapping[int, int],
    own_rating: int,
    target_rank: float,
    config: RatingConfig,
) -> int:
    lower = config.performance_min
    upper = config.performance_max + 1
    while lower < upper - 1:
        middle = (lower + upper) // 2
        if _seed(rating_counts, middle, config.logistic_scale, own_rating) < target_rank:
            upper = middle
        else:
            lower = middle
    return lower


def _expand_competitors(
    contest: Contest,
    normalizer: DefaultNormalizer,
    config: RatingConfig,
) -> tuple[dict[CompetitorId, int], dict[CompetitorId, tuple[str, str]]]:
    ranks: dict[CompetitorId, int] = {}
    display: dict[CompetitorId, tuple[str, str]] = {}
    for team in contest.teams:
        if not team.official or not team.has_activity:
            continue
        if team.rank <= 0:
            raise DataValidationError(
                f"contest {contest.contest_id}, team {team.team_id}: rank must be positive"
            )
        team_competitors: set[CompetitorId] = set()
        if team.rating_competitor is not None:
            display_school = team.rating_display_school
            display_member = team.rating_display_member
            if display_school is None:
                raise DataValidationError(
                    f"contest {contest.contest_id}, team {team.team_id}: "
                    "rating display school must be provided"
                )
            if not display_member or not display_member.strip():
                raise DataValidationError(
                    f"contest {contest.contest_id}, team {team.team_id}: "
                    "rating display member must not be empty"
                )
            competitors = (
                (team.rating_competitor, display_school, display_member),
            )
        else:
            competitors = tuple(
                (normalizer.competitor(team.school_name, member), team.school_name, member)
                for member in team.members
                if member.strip() and not is_coach_name(member)
            )
        for competitor, display_school, display_member in competitors:
            if competitor in team_competitors:
                message = (
                    f"contest {contest.contest_id}, team {team.team_id}: "
                    f"duplicate competitor {competitor}"
                )
                raise IdentityConflictError(message)
            team_competitors.add(competitor)
            if competitor in ranks:
                if config.duplicate_competitor == "error":
                    message = (
                        f"contest {contest.contest_id}: competitor {competitor} "
                        "appears in multiple teams"
                    )
                    raise IdentityConflictError(message)
                if team.rank < ranks[competitor]:
                    ranks[competitor] = team.rank
                    display[competitor] = (display_school, display_member)
                continue
            ranks[competitor] = team.rank
            display[competitor] = (display_school, display_member)
    return ranks, display


def calculate_contest_ratings(
    contest: Contest,
    current_ratings: Mapping[CompetitorId, int] | None = None,
    *,
    normalizer: DefaultNormalizer | None = None,
    config: RatingConfig | None = None,
) -> ContestRatingResult:
    normalizer = normalizer or DefaultNormalizer()
    config = config or RatingConfig()
    before = dict(current_ratings or {})
    ranks, display = _expand_competitors(contest, normalizer, config)
    if not ranks:
        return ContestRatingResult(contest, (), MappingProxyType(before))

    old_ratings = {
        competitor: before.get(competitor, config.initial_rating) for competitor in ranks
    }
    rating_counts = Counter(old_ratings.values())
    raw: dict[CompetitorId, tuple[float, float, int, int]] = {}
    for competitor, rank in ranks.items():
        old_rating = old_ratings[competitor]
        seed = _seed(rating_counts, old_rating, config.logistic_scale)
        target_rank = math.sqrt(seed * rank)
        performance = _performance_rating(rating_counts, old_rating, target_rank, config)
        raw_delta = _trunc_div(performance - old_rating, 2)
        raw[competitor] = (seed, target_rank, performance, raw_delta)

    raw_sum = sum(values[3] for values in raw.values())
    global_correction = -_trunc_div(raw_sum, len(raw)) - 1 if config.apply_global_correction else 0
    corrected = {
        competitor: values[3] + global_correction for competitor, values in raw.items()
    }

    top_correction = 0
    if config.apply_top_correction:
        ordered = sorted(ranks, key=lambda item: (-old_ratings[item], item.school, item.member))
        top_count = min(len(ordered), 4 * math.floor(math.sqrt(len(ordered)) + 0.5))
        top_sum = sum(corrected[competitor] for competitor in ordered[:top_count])
        top_correction = min(max(-_trunc_div(top_sum, top_count), -10), 0)

    changes: list[CompetitorRatingChange] = []
    after = dict(before)
    for competitor in sorted(ranks):
        seed, target_rank, performance, raw_delta = raw[competitor]
        delta = raw_delta + global_correction + top_correction
        new_rating = old_ratings[competitor] + delta
        after[competitor] = new_rating
        display_school, display_member = display[competitor]
        changes.append(
            CompetitorRatingChange(
                competitor=competitor,
                display_school=display_school,
                display_member=display_member,
                old_rating=old_ratings[competitor],
                rank=ranks[competitor],
                seed=seed,
                target_rank=target_rank,
                performance_rating=performance,
                raw_delta=raw_delta,
                global_correction=global_correction,
                top_correction=top_correction,
                delta=delta,
                new_rating=new_rating,
            )
        )
    return ContestRatingResult(contest, tuple(changes), MappingProxyType(after))


def calculate_series_ratings(
    contests: Sequence[Contest],
    initial_ratings: Mapping[CompetitorId, int] | None = None,
    *,
    normalizer: DefaultNormalizer | None = None,
    config: RatingConfig | None = None,
) -> SeriesRatingResult:
    ratings = dict(initial_ratings or {})
    results: list[ContestRatingResult] = []
    normalizer = normalizer or DefaultNormalizer()
    config = config or RatingConfig()
    for contest in contests:
        result = calculate_contest_ratings(
            contest,
            ratings,
            normalizer=normalizer,
            config=config,
        )
        ratings = dict(result.ratings)
        results.append(result)
    return SeriesRatingResult(tuple(results), MappingProxyType(ratings))
