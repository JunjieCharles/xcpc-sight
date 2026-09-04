from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .errors import DataValidationError

_MEDALS = frozenset({"gold", "silver", "bronze"})
_FIELDS = frozenset({"rank", "name", "grade", "score", "medal", "school"})


@dataclass(frozen=True, slots=True)
class IoiResult:
    rank: int
    name: str
    grade: str
    score: float
    medal: str
    school: str

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def parse_ioi_results(
    year: int, max_score: int | float, records: list[Mapping[str, object]]
) -> list[IoiResult]:
    """Validate standardized IOI result records supplied by an explicit source."""
    if year < 1989:
        raise DataValidationError(f"IOI {year}: invalid year")
    if not _is_score(max_score) or max_score <= 0:
        raise DataValidationError(f"IOI {year}: invalid maximum score")

    results = []
    for row_index, record in enumerate(records):
        if set(record) != _FIELDS:
            raise DataValidationError(f"IOI {year} row {row_index}: unexpected fields")
        rank = record["rank"]
        score = record["score"]
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            raise DataValidationError(f"IOI {year} row {row_index}: invalid rank")
        if not _is_score(score) or score < 0 or score > max_score:
            raise DataValidationError(f"IOI {year} row {row_index}: invalid score")
        values = {field: record[field] for field in ("name", "grade", "medal", "school")}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise DataValidationError(f"IOI {year} row {row_index}: missing required value")
        if values["medal"] not in _MEDALS:
            raise DataValidationError(f"IOI {year} row {row_index}: invalid medal")
        results.append(
            IoiResult(
                rank=rank,
                name=values["name"],
                grade=values["grade"],
                score=float(score),
                medal=values["medal"],
                school=values["school"],
            )
        )
    if not results:
        raise DataValidationError(f"IOI {year}: no result records")
    return results


def _is_score(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )