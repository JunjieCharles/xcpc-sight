from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from core.models import CompetitorId, Contest


@dataclass(frozen=True, slots=True)
class RatingConfig:
    initial_rating: int = 1400
    logistic_scale: int = 400
    performance_min: int = 1
    performance_max: int = 7999
    apply_global_correction: bool = True
    apply_top_correction: bool = True
    duplicate_competitor: Literal["best_rank", "error"] = "best_rank"


@dataclass(frozen=True, slots=True)
class CompetitorRatingChange:
    competitor: CompetitorId
    display_school: str
    display_member: str
    old_rating: int
    rank: int
    seed: float
    target_rank: float
    performance_rating: int
    raw_delta: int
    global_correction: int
    top_correction: int
    delta: int
    new_rating: int


@dataclass(frozen=True, slots=True)
class ContestRatingResult:
    contest: Contest
    changes: tuple[CompetitorRatingChange, ...]
    ratings: Mapping[CompetitorId, int]


@dataclass(frozen=True, slots=True)
class SeriesRatingResult:
    contests: tuple[ContestRatingResult, ...]
    ratings: Mapping[CompetitorId, int]
