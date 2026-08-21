import math

import pytest

from problem_rating.problem_features import (
    build_contest_problem_features,
    sliding_window_solve_curve,
)


def test_sliding_window_is_centered_on_reference_rating():
    features = sliding_window_solve_curve(
        ratings=[1399, 1400, 1500, 1600, 1601],
        solved=[False, True, True, False, True],
        centers=[1500],
        half_width=100,
    )

    assert features["participantCountR1500"] == 3
    assert features["solvedCountR1500"] == 2
    assert features["solveRateR1500"] == pytest.approx(2.5 / 4)
    assert features["solveLogitR1500"] == pytest.approx(math.log(2.5 / 1.5))


def test_empty_sliding_window_keeps_count_and_marks_rate_missing():
    features = sliding_window_solve_curve(
        ratings=[1200], solved=[False], centers=[2000], half_width=100
    )

    assert features["participantCountR2000"] == 0
    assert features["solvedCountR2000"] == 0
    assert features["solveRateR2000"] is None
    assert features["solveLogitR2000"] is None


def test_sliding_window_validates_input_lengths():
    with pytest.raises(ValueError):
        sliding_window_solve_curve([1200], [], [1200])


def test_unattempted_and_failed_participants_are_both_unsolved():
    rows = build_contest_problem_features(
        contest_id=1,
        contest={"startTimeSeconds": 100, "durationSeconds": 7200},
        problems=[{"index": "A", "rating": 1200}],
        rating_changes=[
            {"handle": "accepted", "newRating": 1500},
            {"handle": "failed", "newRating": 1500},
            {"handle": "unattempted", "newRating": 1500},
        ],
        submissions=[
            {
                "author": {
                    "participantType": "CONTESTANT",
                    "members": [{"handle": "accepted"}],
                },
                "problem": {"index": "A"},
                "relativeTimeSeconds": 600,
                "verdict": "OK",
            },
            {
                "author": {
                    "participantType": "CONTESTANT",
                    "members": [{"handle": "failed"}],
                },
                "problem": {"index": "A"},
                "relativeTimeSeconds": 500,
                "verdict": "WRONG_ANSWER",
            },
        ],
        centers=[1500],
        half_width=100,
    )

    assert len(rows) == 1
    assert rows[0]["participantCount"] == 3
    assert rows[0]["solvedCount"] == 1
    assert rows[0]["participantCountR1500"] == 3
    assert rows[0]["solvedCountR1500"] == 1
