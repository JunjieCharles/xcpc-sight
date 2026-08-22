"""Problem-level features for difficulty-model experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence

import numpy as np
from scipy.optimize import minimize

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
            result[f"solveRateR{center}"] = (solved_count + 0.5) / (participant_count + 1.0)
            result[f"solveLogitR{center}"] = math.log(
                (solved_count + 0.5) / (participant_count - solved_count + 0.5)
            )

    return result


def kernel_solve_curve(
    ratings: Sequence[float],
    solved: Sequence[bool],
    centers: Sequence[int],
    *,
    bandwidth: float = 100.0,
    kernel: str = "triangular",
) -> dict[str, float | None]:
    """Build a continuous rating-conditioned solve curve.

    ``triangular`` has compact support at ``bandwidth``. ``gaussian`` uses
    ``bandwidth`` as its standard deviation. Effective sample size is emitted
    with every point so the model can distinguish precise and sparse rates.
    """

    if len(ratings) != len(solved):
        raise ValueError("ratings and solved must have the same length")
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")
    if kernel not in {"triangular", "gaussian"}:
        raise ValueError("kernel must be triangular or gaussian")

    rating_values = np.asarray(ratings, dtype=float)
    solved_values = np.asarray(solved, dtype=float)
    prefix = "triangle" if kernel == "triangular" else "gaussian"
    result: dict[str, float | None] = {}

    for center in centers:
        scaled_distance = np.abs(rating_values - center) / bandwidth
        if kernel == "triangular":
            weights = np.maximum(0.0, 1.0 - scaled_distance)
        else:
            weights = np.exp(-0.5 * scaled_distance**2)

        total_weight = float(np.sum(weights))
        squared_weight = float(np.sum(weights**2))
        solved_weight = float(np.sum(weights * solved_values))
        effective_count = total_weight**2 / squared_weight if squared_weight > 0 else 0.0
        result[f"{prefix}ParticipantWeightR{center}"] = total_weight
        result[f"{prefix}SolvedWeightR{center}"] = solved_weight
        result[f"{prefix}EffectiveCountR{center}"] = effective_count

        if total_weight == 0:
            result[f"{prefix}SolveRateR{center}"] = None
            result[f"{prefix}SolveLogitR{center}"] = None
        else:
            result[f"{prefix}SolveRateR{center}"] = (solved_weight + 0.5) / (total_weight + 1.0)
            result[f"{prefix}SolveLogitR{center}"] = math.log(
                (solved_weight + 0.5) / (total_weight - solved_weight + 0.5)
            )

    return result


def fit_irt_solve_curve(
    ratings: Sequence[float],
    solved: Sequence[bool],
    *,
    rating_center: float = 1800.0,
    rating_scale: float = 400.0,
) -> dict[str, float | None]:
    """Fit a monotone two-parameter logistic solve curve for one problem."""

    if len(ratings) != len(solved):
        raise ValueError("ratings and solved must have the same length")
    if rating_scale <= 0:
        raise ValueError("rating_scale must be positive")
    if len(ratings) == 0:
        return {
            "irtRating50": None,
            "irtSlope": None,
            "irtIntercept": None,
        }

    rating_values = np.asarray(ratings, dtype=float)
    solved_values = np.asarray(solved, dtype=float)
    unique_ratings, inverse = np.unique(rating_values, return_inverse=True)
    participant_counts = np.bincount(inverse).astype(float)
    solved_counts = np.bincount(inverse, weights=solved_values).astype(float)
    scaled_ratings = (unique_ratings - rating_center) / rating_scale

    overall_rate = (float(np.sum(solved_values)) + 0.5) / (len(solved_values) + 1.0)
    initial_intercept = math.log(overall_rate / (1.0 - overall_rate))

    def objective(parameters):
        intercept, slope = parameters
        linear_predictor = intercept + slope * scaled_ratings
        negative_log_likelihood = np.sum(
            participant_counts * np.logaddexp(0.0, linear_predictor)
            - solved_counts * linear_predictor
        )
        # Weak regularisation stabilises all/none-solved and sparse tails.
        return float(negative_log_likelihood + 0.05 * (intercept**2 + slope**2))

    fitted = minimize(
        objective,
        x0=np.asarray([initial_intercept, 1.0]),
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0), (0.03, 10.0)],
    )
    intercept, slope = fitted.x
    rating_50 = rating_center - rating_scale * intercept / slope
    return {
        "irtRating50": float(np.clip(rating_50, 0.0, 5000.0)),
        "irtSlope": float(slope),
        "irtIntercept": float(intercept),
    }


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
    has_previous = np.asarray([record[1].has_previous[:3] for record in solve_records], dtype=bool)
    log_elapsed = np.log(np.maximum(elapsed, minimum_time))

    for offset in range(3):
        q25, q50, q75 = np.percentile(log_elapsed[:, offset], [25, 50, 75])
        previous = offset + 1
        result[f"logTimePrev{previous}Median"] = float(q50)
        result[f"logTimePrev{previous}Iqr"] = float(q75 - q25)
        result[f"hasPrev{previous}Rate"] = float(np.mean(has_previous[:, offset]))

    rating_q25, rating_median, rating_q75 = np.percentile(ratings, [25, 50, 75])
    result["solverRatingMedian"] = float(rating_median)
    result["solverRatingIqr"] = float(rating_q75 - rating_q25)
    result["burstUnder60Rate"] = float(np.mean(elapsed[:, 0] < 60))
    result["burstUnder120Rate"] = float(np.mean(elapsed[:, 0] < 120))

    if len(solve_records) < 20:
        result["lowTimeOutlierRate"] = None
    else:
        adjusted_log_time = log_elapsed[:, 0] - rating_coefficient * (ratings - rating_median)
        q25, q75 = np.percentile(adjusted_log_time, [25, 75])
        lower_fence = q25 - 1.5 * (q75 - q25)
        result["lowTimeOutlierRate"] = float(np.mean(adjusted_log_time < lower_fence))

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
    for submission in submissions:
        author = submission.get("author") or {}
        members = author.get("members") or []
        if author.get("participantType") != "CONTESTANT" or not members:
            continue
        handle = members[0].get("handle")
        if handle not in user_ratings:
            continue
        submissions_by_user[handle].append(submission)

    solves_by_user = {
        handle: calculate_solve_features(user_submissions, max_previous=3)
        for handle, user_submissions in submissions_by_user.items()
    }
    handles = list(user_ratings)
    ratings = [user_ratings[handle] for handle in handles]
    rows: list[dict] = []

    for problem_order, problem in enumerate(rated_problems, start=1):
        problem_index = problem["index"]
        solved_flags = [problem_index in solves_by_user.get(handle, {}) for handle in handles]
        solved_count = sum(solved_flags)
        participant_count = len(handles)

        time_records = [
            (user_ratings[handle], solves_by_user[handle][problem_index])
            for handle in handles
            if user_ratings[handle] >= minimum_time_rating
            and problem_index in solves_by_user.get(handle, {})
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
                (solved_count + 0.5) / (participant_count + 1.0) if participant_count else None
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
        row.update(
            kernel_solve_curve(
                ratings,
                solved_flags,
                centers,
                bandwidth=half_width,
                kernel="triangular",
            )
        )
        row.update(
            kernel_solve_curve(
                ratings,
                solved_flags,
                centers,
                bandwidth=half_width,
                kernel="gaussian",
            )
        )
        row.update(fit_irt_solve_curve(ratings, solved_flags))
        row.update(summarize_solve_times(time_records))
        rows.append(row)

    return rows
