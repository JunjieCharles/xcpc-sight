import math
from itertools import permutations

import pytest

from core.errors import DataValidationError
from rating import normalized_lse_rating


@pytest.mark.parametrize("value", [-2000, 0, 1400, 2000, 100000])
def test_equal_members_keep_individual_scale(value):
    assert normalized_lse_rating([value] * 3) == value
    assert normalized_lse_rating([value]) == value


def test_normalized_lse_golden_vectors_and_ordering():
    assert normalized_lse_rating([]) is None
    assert normalized_lse_rating([2000, 1600, 1600]) == pytest.approx(1840.823996531185)
    assert normalized_lse_rating([2000, 1400, 1400]) == pytest.approx(1819.8049281306448)
    assert normalized_lse_rating([1900] * 3) > normalized_lse_rating([2000, 1400, 1400])
    values = [2100, 1500, 1700]
    result = normalized_lse_rating(values)
    assert sum(values) / 3 < result < max(values)
    assert all(normalized_lse_rating(row) == result for row in permutations(values))
    assert normalized_lse_rating([value + 100000 for value in values]) == pytest.approx(
        result + 100000
    )


@pytest.mark.parametrize("bad", [None, True, "1400", math.nan, math.inf, -math.inf])
def test_invalid_member_rating_has_context(bad):
    with pytest.raises(DataValidationError, match=r"team ratings\[1\]"):
        normalized_lse_rating([1400, bad])
