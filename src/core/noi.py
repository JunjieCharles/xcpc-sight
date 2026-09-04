from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .errors import DataValidationError

_MEDALS = {"金": "gold", "银": "silver", "铜": "bronze"}
_MEDAL_HEADING = re.compile(r"^([金银铜])牌\d+名$")


@dataclass(frozen=True, slots=True)
class NoiAward:
    year: int
    name: str
    province: str
    school: str
    grade: str
    score: int
    medal: str

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def parse_noi_awards(year: int, rows: list[list[object]]) -> list[NoiAward]:
    """Extract the public, normalized fields from a rendered NOI award table."""
    if year < 1984:
        raise DataValidationError(f"NOI {year}: invalid year")

    awards: list[NoiAward] = []
    medal: str | None = None
    columns: dict[str, int] | None = None
    for row_index, raw_row in enumerate(rows):
        row = [str(value).strip() for value in raw_row]
        if len(row) == 1:
            matched = _MEDAL_HEADING.fullmatch(row[0])
            if matched:
                medal = _MEDALS[matched.group(1)]
            continue
        if row and row[0] == "证书编号":
            columns = _required_columns(year, row_index, row)
            continue
        if not row or not row[0].startswith("CCF-NOI"):
            continue
        if medal is None or columns is None:
            raise DataValidationError(f"NOI {year} row {row_index}: missing medal or column header")
        awards.append(
            NoiAward(
                year=year,
                name=_value(year, row_index, row, columns["name"]),
                province=_value(year, row_index, row, columns["province"]),
                school=_value(year, row_index, row, columns["school"]),
                grade=_value(year, row_index, row, columns["grade"]),
                score=_score(year, row_index, _value(year, row_index, row, columns["score"])),
                medal=medal,
            )
        )
    if not awards:
        raise DataValidationError(f"NOI {year}: no award records")
    return awards


def _required_columns(year: int, row_index: int, header: list[str]) -> dict[str, int]:
    labels = {
        "name": "姓名",
        "province": "省份",
        "school": "学校",
        "grade": "年级",
        "score": "总分",
    }
    columns: dict[str, int] = {}
    for field, label in labels.items():
        for index, value in enumerate(header):
            if value == label or (field in {"school", "grade"} and value.startswith(label)):
                columns[field] = index
                break
        else:
            raise DataValidationError(f"NOI {year} row {row_index}: missing {label} column")
    return columns


def _value(year: int, row_index: int, row: list[str], column: int) -> str:
    if column >= len(row) or not row[column]:
        raise DataValidationError(f"NOI {year} row {row_index}: missing required value")
    return row[column]


def _score(year: int, row_index: int, value: str) -> int:
    try:
        score = int(value)
    except ValueError as error:
        message = f"NOI {year} row {row_index}: invalid total score {value!r}"
        raise DataValidationError(message) from error
    if score < 0:
        raise DataValidationError(f"NOI {year} row {row_index}: negative total score")
    return score