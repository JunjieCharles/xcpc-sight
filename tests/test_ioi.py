from __future__ import annotations

import pytest

from core import DataValidationError, parse_ioi_results


def test_parse_ioi_results_preserves_ties_and_decimal_scores() -> None:
    results = parse_ioi_results(
        2026,
        600,
        [
            {
                "rank": 1,
                "name": "甲",
                "grade": "高二",
                "score": 498.27,
                "medal": "gold",
                "school": "学校甲",
            },
            {
                "rank": 1,
                "name": "乙",
                "grade": "高三",
                "score": 498.27,
                "medal": "gold",
                "school": "学校乙",
            },
        ],
    )

    assert [result.to_document() for result in results] == [
        {
            "rank": 1,
            "name": "甲",
            "grade": "高二",
            "score": 498.27,
            "medal": "gold",
            "school": "学校甲",
        },
        {
            "rank": 1,
            "name": "乙",
            "grade": "高三",
            "score": 498.27,
            "medal": "gold",
            "school": "学校乙",
        },
    ]


@pytest.mark.parametrize(
    "record, message",
    [
        (
            {
                "rank": 0,
                "name": "甲",
                "grade": "高二",
                "score": 0,
                "medal": "gold",
                "school": "学校甲",
            },
            "invalid rank",
        ),
        (
            {
                "rank": 1,
                "name": "甲",
                "grade": "高二",
                "score": 601,
                "medal": "gold",
                "school": "学校甲",
            },
            "invalid score",
        ),
        (
            {
                "rank": 1,
                "name": "甲",
                "grade": "高二",
                "score": 1,
                "medal": "platinum",
                "school": "学校甲",
            },
            "invalid medal",
        ),
    ],
)
def test_parse_ioi_results_rejects_invalid_values(record, message: str) -> None:
    with pytest.raises(DataValidationError, match=message):
        parse_ioi_results(2026, 600, [record])