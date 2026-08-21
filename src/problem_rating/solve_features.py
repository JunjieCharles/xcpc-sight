"""Solve-time features derived only from accepted submission timestamps."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


def get_problem_root(index: str) -> str:
    """Return the common root used by split problems such as F1 and F2."""

    root = index.rstrip("0123456789")
    return root or index


@dataclass(frozen=True)
class SolveFeatures:
    """Features for the first accepted submission of one problem."""

    accepted_time: float
    elapsed_since_previous: tuple[float, ...]
    has_previous: tuple[bool, ...]
    accepted_order: int


def calculate_solve_features(
    submissions: Iterable[Mapping],
    *,
    max_previous: int = 3,
    minimum_elapsed: float = 1.0,
) -> dict[str, SolveFeatures]:
    """Calculate prev1..prevN elapsed times without using first attempts.

    Only the first accepted submission for each problem is used. A previous
    accepted problem with the same root (for example F1 when processing F2)
    is not used as a boundary. When fewer than ``max_previous`` boundaries
    exist, contest start (relative time zero) is used and ``has_previous``
    records that the corresponding boundary was missing.
    """

    if max_previous < 1:
        raise ValueError("max_previous must be at least 1")
    if minimum_elapsed <= 0:
        raise ValueError("minimum_elapsed must be positive")

    first_accepts: dict[str, float] = {}
    for submission in submissions:
        if submission.get("verdict") != "OK":
            continue

        problem = submission.get("problem") or {}
        problem_index = problem.get("index")
        accepted_time = submission.get("relativeTimeSeconds")
        if problem_index is None or accepted_time is None:
            continue

        accepted_time = float(accepted_time)
        previous = first_accepts.get(problem_index)
        if previous is None or accepted_time < previous:
            first_accepts[problem_index] = accepted_time

    ordered_accepts = sorted(first_accepts.items(), key=lambda item: item[1])
    results: dict[str, SolveFeatures] = {}

    for accepted_order, (problem_index, accepted_time) in enumerate(ordered_accepts, start=1):
        current_root = get_problem_root(problem_index)
        previous_times = [
            previous_time
            for previous_index, previous_time in reversed(ordered_accepts[: accepted_order - 1])
            if get_problem_root(previous_index) != current_root
        ]

        elapsed: list[float] = []
        has_previous: list[bool] = []
        for offset in range(max_previous):
            boundary_exists = offset < len(previous_times)
            boundary = previous_times[offset] if boundary_exists else 0.0
            elapsed.append(max(accepted_time - boundary, minimum_elapsed))
            has_previous.append(boundary_exists)

        results[problem_index] = SolveFeatures(
            accepted_time=accepted_time,
            elapsed_since_previous=tuple(elapsed),
            has_previous=tuple(has_previous),
            accepted_order=accepted_order,
        )

    return results


def calculate_problem_times(
    submissions: Iterable[Mapping],
    contest_start_time: float = 0,
    *,
    minimum_elapsed: float = 1.0,
) -> dict[str, float]:
    """Return prev1 elapsed time for backward-compatible callers.

    ``contest_start_time`` is retained for API compatibility. Codeforces
    submissions already provide relative times, so the value is not used.
    """

    return {
        problem_index: features.elapsed_since_previous[0]
        for problem_index, features in calculate_solve_features(
            submissions,
            max_previous=1,
            minimum_elapsed=minimum_elapsed,
        ).items()
    }
