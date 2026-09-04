from __future__ import annotations

import json

import pytest

from core import DataValidationError
from core.noi import parse_noi_awards
from scripts.normalize_noi_awards import build_documents


def test_parse_noi_awards_extracts_requested_fields_and_medals() -> None:
    awards = parse_noi_awards(
        2025,
        [
            ["CCF NOI2025获奖名单"],
            ["金牌1名"],
            ["证书编号", "姓名", "省份", "学校(全称)", "年级（暑假前）", "总分", "集训队"],
            ["CCF-NOI25-001", "甲", "浙江", "学校甲", "高二", "650", "是"],
            ["银牌1名"],
            ["CCF-NOI25-002", "乙", "北京", "学校乙", "高一", "600", "否"],
        ],
    )

    assert [award.to_document() for award in awards] == [
        {
            "year": 2025,
            "name": "甲",
            "province": "浙江",
            "school": "学校甲",
            "grade": "高二",
            "score": 650,
            "medal": "gold",
        },
        {
            "year": 2025,
            "name": "乙",
            "province": "北京",
            "school": "学校乙",
            "grade": "高一",
            "score": 600,
            "medal": "silver",
        },
    ]


def test_parse_noi_awards_rejects_non_numeric_total_score() -> None:
    with pytest.raises(DataValidationError, match="invalid total score"):
        parse_noi_awards(
            2025,
            [
                ["金牌1名"],
                ["证书编号", "姓名", "省份", "学校", "年级", "总分"],
                ["CCF-NOI25-001", "甲", "浙江", "学校甲", "高二", "六百"],
            ],
        )


def test_build_documents_creates_year_documents_and_source_index(tmp_path) -> None:
    (tmp_path / "2025.json").write_text(
        json.dumps(
            [
                ["金牌1名"],
                ["证书编号", "姓名", "省份", "学校", "年级", "总分"],
                ["CCF-NOI25-001", "甲", "浙江", "学校甲", "高二", "650"],
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "years": {
                    "2025": {
                        "cache_file": "2025.json",
                        "source_url": "https://example.test/noi-2025.htm",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    index, documents = build_documents(tmp_path)

    assert index == {
        "schemaVersion": 1,
        "years": [
            {"year": 2025, "path": "2025.json", "sourceUrl": "https://example.test/noi-2025.htm"}
        ],
    }
    assert documents[2025]["awards"] == [
        {
            "year": 2025,
            "name": "甲",
            "province": "浙江",
            "school": "学校甲",
            "grade": "高二",
            "score": 650,
            "medal": "gold",
        }
    ]