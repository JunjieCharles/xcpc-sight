import math

import pytest

from scripts.analyze_team_aggregation import aggregate, rho, top_recall


def test_aggregation_limits_and_missing_count_effect():
    assert aggregate([1500, 1500, 1500], "lse") == pytest.approx(1500)
    assert aggregate([2000], "lse") == pytest.approx(2000)
    values = [1200, 1600, 2000]
    expected = 2000 + 400 * math.log10(1.11 / 3)
    assert aggregate(values, "lse") == pytest.approx(expected)
    assert aggregate(values, "sum_lse") - aggregate(values, "lse") == pytest.approx(
        400 * math.log10(3)
    )
    assert aggregate(values, "blend", 0.75) == 1900
    assert aggregate(values, "lse", 0.01) == pytest.approx(2000, abs=0.01)


def test_metrics_handle_ties_without_input_order_advantage():
    assert rho([30, 20, 20, 10], [1, 2, 2, 4]) == pytest.approx(1)
    assert top_recall([10, 10, 0], [1, 2, 3], 1) == pytest.approx(0.5)
    assert top_recall([0, 10, 10], [3, 2, 1], 1) == pytest.approx(0.5)
