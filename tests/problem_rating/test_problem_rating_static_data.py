import csv
import json
from pathlib import Path

import pytest

from core.errors import DataValidationError
from problem_rating import (
    MODEL_ID,
    ProblemRatingRecord,
    problem_index_sort_key,
    project_problem_rating_index,
    project_problem_rating_series,
)
from scripts.generate_problem_rating_static_data import (
    REQUIRED_COLUMNS,
    generate_problem_rating_static_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def rating_series(series_id: str = "nowcoder-summer-2026") -> dict[str, object]:
    source = (
        "nowcoder"
        if series_id.startswith("nowcoder")
        else "hdu"
        if series_id.startswith("hdu")
        else ""
    )

    def contest_id(native_id: str) -> str:
        return f"{source}:{native_id}" if source else native_id

    return {
        "schemaVersion": 1,
        "id": series_id,
        "title": "Example series",
        "initialRating": 1400,
        "contests": [
            {
                "id": contest_id("10"),
                "title": "Contest 10",
                "collection": series_id,
                "startAt": "2026-07-01T12:00:00+08:00",
            },
            {
                "id": contest_id("11"),
                "title": "Contest 11",
                "collection": series_id,
                "startAt": "2026-07-03T12:00:00+08:00",
            },
        ],
        "competitors": [],
    }


def record(
    native_contest_id: str,
    problem_index: str,
    *,
    series_id: str = "nowcoder-summer-2026",
    rating: int = 1700,
    problem_name: str | None = None,
) -> ProblemRatingRecord:
    return ProblemRatingRecord(
        series_id=series_id,
        native_contest_id=native_contest_id,
        contest_name=f"Contest {native_contest_id}",
        problem_index=problem_index,
        problem_name=problem_name or f"Problem {problem_index}",
        solved_count=20,
        participant_count=100,
        time_sample_count=10,
        predicted_rating=rating,
    )


def test_project_problem_rating_series_uses_canonical_contests_and_natural_order() -> None:
    document = project_problem_rating_series(
        [record("11", "A"), record("10", "A10"), record("10", "A2")],
        rating_series(),
    )

    assert document == {
        "schemaVersion": 1,
        "seriesId": "nowcoder-summer-2026",
        "title": "Example series",
        "modelId": MODEL_ID,
        "contests": [
            {
                "id": "nowcoder:10",
                "title": "Contest 10",
                "startAt": "2026-07-01T12:00:00+08:00",
                "problems": [
                    {
                        "index": "A2",
                        "name": "Problem A2",
                        "rating": 1700,
                        "solvedCount": 20,
                        "participantCount": 100,
                        "timeSampleCount": 10,
                    },
                    {
                        "index": "A10",
                        "name": "Problem A10",
                        "rating": 1700,
                        "solvedCount": 20,
                        "participantCount": 100,
                        "timeSampleCount": 10,
                    },
                ],
            },
            {
                "id": "nowcoder:11",
                "title": "Contest 11",
                "startAt": "2026-07-03T12:00:00+08:00",
                "problems": [
                    {
                        "index": "A",
                        "name": "Problem A",
                        "rating": 1700,
                        "solvedCount": 20,
                        "participantCount": 100,
                        "timeSampleCount": 10,
                    }
                ],
            },
        ],
    }
    assert problem_index_sort_key("A2") < problem_index_sort_key("A10")


def test_projection_leaves_known_missing_problem_names_blank() -> None:
    document = project_problem_rating_series(
        [
            record("10", "A", problem_name="官方 guest 数据未提供题名"),
            record("11", "A"),
        ],
        rating_series(),
    )

    assert document["contests"][0]["problems"][0]["name"] == ""


def test_projection_publishes_configured_icpc_ccpc_short_titles() -> None:
    series = rating_series("2025-2026")
    series["contests"][0]["id"] = "icpc2025preliminary-1"
    series["contests"][1]["id"] = "ccpc2025final"

    document = project_problem_rating_series(
        [
            record("icpc2025preliminary-1", "A", series_id="2025-2026"),
            record("ccpc2025final", "A", series_id="2025-2026"),
        ],
        series,
    )

    assert [contest["shortTitle"] for contest in document["contests"]] == [
        "ICPC 网络赛1",
        "CCPC 总决赛",
    ]


def test_projection_rejects_ambiguous_or_inconsistent_predictions() -> None:
    with pytest.raises(DataValidationError, match="duplicate record"):
        project_problem_rating_series(
            [record("10", "A"), record("10", "A"), record("11", "A")],
            rating_series(),
        )
    with pytest.raises(DataValidationError, match="no problem ratings"):
        project_problem_rating_series([record("10", "A")], rating_series())
    with pytest.raises(DataValidationError, match="time_sample_count exceeds"):
        ProblemRatingRecord(
            series_id="nowcoder-summer-2026",
            native_contest_id="10",
            contest_name="Contest",
            problem_index="A",
            problem_name="Problem",
            solved_count=1,
            participant_count=2,
            time_sample_count=2,
            predicted_rating=1500,
        )


def test_problem_rating_index_preserves_canonical_series_order() -> None:
    nowcoder = project_problem_rating_series(
        [record("10", "A"), record("11", "A")], rating_series()
    )
    hdu = project_problem_rating_series(
        [
            record("10", "1001", series_id="hdu-summer-2026"),
            record("11", "1001", series_id="hdu-summer-2026"),
        ],
        rating_series("hdu-summer-2026"),
    )

    index = project_problem_rating_index(
        [(hdu, "series/hdu.json"), (nowcoder, "series/nowcoder.json")]
    )

    assert [item["id"] for item in index["series"]] == [
        "hdu-summer-2026",
        "nowcoder-summer-2026",
    ]


def write_prediction_csv(path, records: list[ProblemRatingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for item in records:
            writer.writerow(
                {
                    "series": item.series_id,
                    "nativeContestId": item.native_contest_id,
                    "contestName": item.contest_name,
                    "problemIndex": item.problem_index,
                    "problemName": item.problem_name,
                    "solvedCount": item.solved_count,
                    "participantCount": item.participant_count,
                    "timeSampleCount": item.time_sample_count,
                    "predictedRating": item.predicted_rating,
                }
            )


def test_offline_generator_publishes_series_before_index(tmp_path) -> None:
    rating_data = tmp_path / "rating-data"
    output = tmp_path / "problem-rating"
    (rating_data / "series").mkdir(parents=True)
    nowcoder = rating_series()
    hdu = rating_series("hdu-summer-2026")
    rankland = rating_series("2025-2026")
    (rating_data / "series" / "nowcoder.json").write_text(json.dumps(nowcoder), encoding="utf-8")
    (rating_data / "series" / "hdu.json").write_text(json.dumps(hdu), encoding="utf-8")
    (rating_data / "series" / "rankland.json").write_text(json.dumps(rankland), encoding="utf-8")
    (rating_data / "index.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "defaultSeriesId": "hdu-summer-2026",
                "series": [
                    {
                        "id": "hdu-summer-2026",
                        "title": "HDU",
                        "path": "series/hdu.json",
                    },
                    {
                        "id": "nowcoder-summer-2026",
                        "title": "Nowcoder",
                        "path": "series/nowcoder.json",
                    },
                    {
                        "id": "2025-2026",
                        "title": "ICPC + CCPC",
                        "path": "series/rankland.json",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    csv_path = tmp_path / "predictions.csv"
    write_prediction_csv(
        csv_path,
        [
            record("10", "A"),
            record("11", "A"),
            record("10", "1001", series_id="hdu-summer-2026"),
            record("11", "1001", series_id="hdu-summer-2026"),
            record("10", "A", series_id="2025-2026"),
            record("11", "A", series_id="2025-2026"),
        ],
    )

    generate_problem_rating_static_data(csv_path, rating_data, output)

    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in index["series"]] == [
        "hdu-summer-2026",
        "nowcoder-summer-2026",
        "2025-2026",
    ]
    published = json.loads(
        (output / "series" / "nowcoder-summer-2026.json").read_text(encoding="utf-8")
    )
    assert published["contests"][0]["problems"][0]["rating"] == 1700
    assert "competitors" not in published


def test_committed_problem_rating_data_matches_canonical_series_without_identities() -> None:
    problem_root = PROJECT_ROOT / "static" / "data" / "problem-rating"
    rating_root = PROJECT_ROOT / "static" / "data"
    index = json.loads((problem_root / "index.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in index["series"]] == [
        "hdu-summer-2026",
        "nowcoder-summer-2026",
        "2025-2026",
    ]
    expected_counts = {
        "hdu-summer-2026": 121,
        "nowcoder-summer-2026": 128,
        "2025-2026": 205,
    }
    expected_icpc_ccpc_short_titles = [
        "ICPC 网络赛1",
        "ICPC 网络赛2",
        "CCPC 网络赛",
        "ICPC 西安",
        "ICPC 成都",
        "ICPC 武汉",
        "CCPC 哈尔滨",
        "ICPC 南京",
        "CCPC 济南",
        "ICPC 沈阳",
        "CCPC 郑州",
        "ICPC 上海",
        "CCPC 重庆",
        "ICPC 香港",
        "ICPC EC-Final",
        "CCPC 总决赛",
    ]
    allowed_problem_fields = {
        "index",
        "name",
        "rating",
        "solvedCount",
        "participantCount",
        "timeSampleCount",
    }
    for entry in index["series"]:
        document = json.loads((problem_root / entry["path"]).read_text(encoding="utf-8"))
        canonical = json.loads(
            (rating_root / "series" / f"{entry['id']}.json").read_text(encoding="utf-8")
        )
        assert [contest["id"] for contest in document["contests"]] == [
            contest["id"] for contest in canonical["contests"]
        ]
        problems = [problem for contest in document["contests"] for problem in contest["problems"]]
        assert len(problems) == expected_counts[entry["id"]]
        assert all(set(problem) == allowed_problem_fields for problem in problems)
        if entry["id"] == "2025-2026":
            assert [contest["shortTitle"] for contest in document["contests"]] == (
                expected_icpc_ccpc_short_titles
            )
        assert "competitors" not in document
