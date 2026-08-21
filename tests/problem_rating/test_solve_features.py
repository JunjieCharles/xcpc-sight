import pytest

from problem_rating.solve_features import (
    calculate_problem_times,
    calculate_solve_features,
    get_problem_root,
)


def submission(index, relative_time, verdict="OK"):
    return {
        "problem": {"index": index},
        "relativeTimeSeconds": relative_time,
        "creationTimeSeconds": relative_time,
        "verdict": verdict,
    }


def test_problem_root_handles_split_problems():
    assert get_problem_root("F1") == "F"
    assert get_problem_root("F2") == "F"
    assert get_problem_root("A") == "A"


def test_prev_features_do_not_use_first_failed_submission():
    submissions = [
        submission("B", 100, "WRONG_ANSWER"),
        submission("A", 300),
        submission("B", 360),
        submission("C", 900),
    ]

    features = calculate_solve_features(submissions, max_previous=3)

    assert features["A"].elapsed_since_previous == (300, 300, 300)
    assert features["B"].elapsed_since_previous == (60, 360, 360)
    assert features["B"].has_previous == (True, False, False)
    assert features["C"].elapsed_since_previous == (540, 600, 900)
    assert calculate_problem_times(submissions)["B"] == 60


def test_only_first_accept_is_used_even_when_input_is_unsorted():
    submissions = [
        submission("A", 500),
        submission("B", 700),
        submission("A", 300),
    ]

    features = calculate_solve_features(submissions, max_previous=1)

    assert features["A"].accepted_time == 300
    assert features["B"].elapsed_since_previous == (400,)


def test_split_problem_does_not_bound_its_sibling():
    submissions = [
        submission("E", 1000),
        submission("F1", 1500),
        submission("F2", 1800),
    ]

    features = calculate_solve_features(submissions, max_previous=2)

    assert features["F2"].elapsed_since_previous == (800, 1800)


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        calculate_solve_features([], max_previous=0)
