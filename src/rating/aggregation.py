"""Pure team aggregation; independent of individual rating updates."""

import math
from collections.abc import Iterable

from core.errors import DataValidationError


def normalized_lse_rating(ratings: Iterable[int | float]) -> float | None:
    """Return 400*log10(mean(10**(rating/400))), or None for no members.

    Callers decide which members are eligible. Missing values must be excluded
    explicitly; no rookie prior is added. Equal ratings retain their exact value.
    """
    values = list(ratings)
    for index, value in enumerate(values):
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            raise DataValidationError(f"team ratings[{index}]: expected a finite number")
    if not values:
        return None
    peak = max(values)
    return peak + 400 * math.log10(
        math.fsum(10 ** ((value - peak) / 400) for value in values) / len(values)
    )
