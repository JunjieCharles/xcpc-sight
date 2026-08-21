"""Problem-level features for difficulty-model experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Mapping, Sequence

import numpy as np

from .solve_features import SolveFeatures, calculate_solve_features


def sliding_window_solve_curve(
    ratings: Sequence[float],
    solved: Sequence[bool],
    centers: Sequence[int],
    *,
    half_width: int = 100,
) -> dict[str, float | int | None]:
    """Build overlapping, rating-centred conditional solve-rate features."""

    if len(ratings) != len(solved):
        raise ValueError("ratings and solved must have the same length")
    if half_width <= 0:
        raise ValueError("half_width must be positive")

    rating_values = np.asarray(ratings, dtype=float)
    solved_values = np.asarray(solved, dtype=bool)
    result: dict[str, float | int | None] = {}

    for center in centers:
        in_window = np.abs(rating_values - center) <= half_width
        participant_count = int(np.count_nonzero(in_window))
        solved_count = int(np.count_nonzero(solved_values & in_window))

        result[f"participantCountR{center}"] = participant_count
        result[f"solvedCountR{center}"] = solved_count
        if participant_count == 0:
            result[f"solveRateR{center}"] = None
            result[f"solveLogitR{center}"] = None
        else:
            # Jeffreys smoothing keeps zero/all-solved windows finite.
            result[f"solveRateR{center}"] = (solved_count + 0.5) / (
                participant_count + 1.0
            )
            result[f"solveLogitR{center}"] = math.log(
                (solved_count + 0.5)
                / (participant_count - solved_count + 0.5)
            )

    return result


def summarize_solve_times(
    solve_records: Sequence[tuple[float, SolveFeatures]],
    *,
    minimum_time: float = 60.0,
    rating_coefficient: float = -0.0011,
) -> dict[str, float | int | None]:
    """Aggregate robust prev1..prev3 statistics for one problem."""

    result: dict[str, float | int | None] = {
        "timeSampleCount": len(solve_records),
    }
    if not solve_records:
        for previous in range(1, 4):
            result[f"logTimePrev{previous}Median"] = None
            result[f"logTimePrev{previous}Iqr"] = None
            result[f"hasPrev{previous}Rate"] = None
        result.update(
            {
                "solverRatingMedian": None,
                "solverRatingIqr": None,
                "burstUnder60Rate": None,
                "burstUnder120Rate": None,
                "lowTimeOutlierRate": None,
            }
        )
        return result

    ratings = np.asarray([record[0] for record in solve_records], dtype=float)
    elapsed = np.asarray(
        [record[1].elapsed_since_previous[:3] for record in solve_records],
        dtype=float,
    )
    has_previous = np.asarray(
        [record[1].has_previous[:3] for record in solve_records], dtype=bool
    )
    log_elapsed = np.log(np.maximum(elapsed, minimum_time))

    for offset in range(3):
        q25, q50, q75 = np.percentile(log_elapsed[:, offset], [25, 50, 75])
        previous = offset + 1
        result[f"logTimePrev{previous}Median"] = float(q50)
        result[f"logTimePrev{previous}Iqr"] = float(q75 - q25)
        result[f"hasPrev{previous}Rate"] = float(np.mean(has_previous[:, offset]))

    rating_q25, rating_median, rating_q75 = np.percentile(
        ratings, [25, 50, 75]
    )
    result["solverRatingMedian"] = float(rating_median)
    result["solverRatingIqr"] = float(rating_q75 - rating_q25)
    result["burstUnder60Rate"] = float(np.mean(elapsed[:, 0] < 60))
    result["burstUnder120Rate"] = float(np.mean(elapsed[:, 0] < 120))

    if len(solve_records) < 20:
        result["lowTimeOutlierRate"] = None
    else:
        adjusted_log_time = log_elapsed[:, 0] - rating_coefficient * (
            ratings - rating_median
        )
        q25, q75 = np.percentile(adjusted_log_time, [25, 75])
        lower_fence = q25 - 1.5 * (q75 - q25)
        result["lowTimeOutlierRate"] = float(
            np.mean(adjusted_log_time < lower_fence)
        )

    return result


def build_contest_problem_features(
    *,
    contest_id: int,
    contest: Mapping,
    problems: Sequence[Mapping],
    rating_changes: Sequence[Mapping],
    submissions: Sequence[Mapping],
    centers: Sequence[int],
    half_width: int = 100,
    minimum_time_rating: int = 1600,
) -> list[dict]:
    """Create one feature row per officially rated problem in a contest."""

    rated_problems = [problem for problem in problems if "rating" in problem]
    user_ratings = {
        change["handle"]: float(change["newRating"])
        for change in rating_changes
        if "newRating" in change
    }
    submissions_by_user: dict[str, list[Mapping]] = defaultdict(list)
    team_sizes: dict[str, int] = {}

    for submission in submissions:
        author = submission.get("author") or {}
        members = author.get("members") or []
        if author.get("participantType") != "CONTESTANT" or not members:
            continue
        handle = members[0].get("handle")
        if handle not in user_ratings:
            continue
        submissions_by_user[handle].append(submission)
        team_sizes[handle] = len(members)

    solves_by_user = {
        handle: calculate_solve_features(user_submissions, max_previous=3)
        for handle, user_submissions in submissions_by_user.items()
    }
    handles = list(user_ratings)
    ratings = [user_ratings[handle] for handle in handles]
    rows: list[dict] = []

    for problem_order, problem in enumerate(rated_problems, start=1):
        problem_index = problem["index"]
        solved_flags = [
            problem_index in solves_by_user.get(handle, {}) for handle in handles
        ]
        solved_count = sum(solved_flags)
        participant_count = len(handles)

        time_records = [
            (user_ratings[handle], solves_by_user[handle][problem_index])
            for handle in handles
            if user_ratings[handle] >= minimum_time_rating
            and problem_index in solves_by_user.get(handle, {})
        ]
        solved_team_sizes = [
            team_sizes.get(handle, 1)
            for handle in handles
            if problem_index in solves_by_user.get(handle, {})
        ]

        row = {
            "contestId": contest_id,
            "contestStartTimeSeconds": contest.get("startTimeSeconds"),
            "contestDurationSeconds": contest.get("durationSeconds"),
            "problemIndex": problem_index,
            "problemRating": problem["rating"],
            "problemOrder": problem_order,
            "ratedProblemCount": len(rated_problems),
            "participantCount": participant_count,
            "solvedCount": solved_count,
            "solveRate": (
                (solved_count + 0.5) / (participant_count + 1.0)
                if participant_count
                else None
            ),
            "teamSizeMedian": (
                float(median(solved_team_sizes)) if solved_team_sizes else None
            ),
        }
        row.update(
            sliding_window_solve_curve(
                ratings,
                solved_flags,
                centers,
                half_width=half_width,
            )
        )
        row.update(summarize_solve_times(time_records))
        rows.append(row)

    return rows
