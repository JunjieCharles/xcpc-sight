from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from core import CompetitorId, Contest, DataValidationError
from rating import (
    CompetitorRatingChange,
    ContestRatingResult,
    SeriesRatingResult,
    project_series_rating_data,
    project_static_data_index,
)
from scripts import generate_static_data


def change(
    competitor: CompetitorId,
    display_school: str,
    display_member: str,
    before: int,
    delta: int,
    rank: int,
) -> CompetitorRatingChange:
    return CompetitorRatingChange(
        competitor=competitor,
        display_school=display_school,
        display_member=display_member,
        old_rating=before,
        rank=rank,
        seed=1.0,
        target_rank=1.0,
        performance_rating=before + 2 * delta,
        raw_delta=delta,
        global_correction=0,
        top_correction=0,
        delta=delta,
        new_rating=before + delta,
    )


def result_fixture() -> tuple[SeriesRatingResult, CompetitorId, CompetitorId]:
    alice = CompetitorId("测试大学", "甲")
    bob = CompetitorId("另一大学", "乙")
    first = Contest("first", "第一场", "ccpc2025", datetime(2025, 10, 1, 9), ())
    second = Contest(
        "second",
        "第二场",
        "icpc2025",
        datetime(2025, 10, 2, 1, tzinfo=UTC),
        (),
    )
    first_changes = (
        change(alice, "测试大学", "甲", 1400, 20, 1),
        change(bob, "另一大学", "乙", 1400, 0, 2),
    )
    second_changes = (change(alice, "測試大學", "甲同学", 1420, -20, 1),)
    first_ratings = MappingProxyType({alice: 1420, bob: 1400})
    final_ratings = MappingProxyType({alice: 1400, bob: 1400})
    result = SeriesRatingResult(
        (
            ContestRatingResult(first, first_changes, first_ratings),
            ContestRatingResult(second, second_changes, final_ratings),
        ),
        final_ratings,
    )
    return result, alice, bob


def stable_id(competitor: CompetitorId) -> str:
    digest = hashlib.sha256(
        f"{competitor.school}\0{competitor.member}".encode()
    ).hexdigest()
    return f"c_{digest}"


def project_fixture() -> dict[str, object]:
    result, _, _ = result_fixture()
    return project_series_rating_data(
        result,
        series_id="2025-2026",
        title="2025–2026 ICPC + CCPC",
    )


def test_projects_exact_index_and_series_structure() -> None:
    result, alice, bob = result_fixture()
    document = project_series_rating_data(
        result,
        series_id="2025-2026",
        title="2025–2026 ICPC + CCPC",
    )

    assert project_static_data_index(
        series_id="2025-2026",
        title="2025–2026 ICPC + CCPC",
        path="series/2025-2026.json",
    ) == {
        "schemaVersion": 1,
        "defaultSeriesId": "2025-2026",
        "series": [
            {
                "id": "2025-2026",
                "title": "2025–2026 ICPC + CCPC",
                "path": "series/2025-2026.json",
            }
        ],
    }
    assert document["contests"] == [
        {
            "id": "first",
            "title": "第一场",
            "collection": "ccpc2025",
            "startAt": "2025-10-01T09:00:00+08:00",
        },
        {
            "id": "second",
            "title": "第二场",
            "collection": "icpc2025",
            "startAt": "2025-10-02T09:00:00+08:00",
        },
    ]
    competitors = document["competitors"]
    assert isinstance(competitors, list)
    assert [item["id"] for item in competitors] == sorted([stable_id(alice), stable_id(bob)])
    assert [item["rank"] for item in competitors] == [1, 1]
    alice_document = next(item for item in competitors if item["id"] == stable_id(alice))
    bob_document = next(item for item in competitors if item["id"] == stable_id(bob))
    assert alice_document["school"] == "測試大學"
    assert alice_document["member"] == "甲同学"
    assert alice_document["contestsParticipated"] == 2
    assert bob_document["participations"] == [
        {
            "contestIndex": 0,
            "contestRank": 2,
            "before": 1400,
            "delta": 0,
            "after": 1400,
        }
    ]


def test_competition_ranking_skips_positions_after_ties() -> None:
    competitors = tuple(CompetitorId("大学", name) for name in ("甲", "乙", "丙"))
    contest = Contest("only", "单场", "icpc2025", datetime(2025, 10, 1, 9), ())
    changes = (
        change(competitors[0], "大学", "甲", 1400, 100, 1),
        change(competitors[1], "大学", "乙", 1400, 100, 1),
        change(competitors[2], "大学", "丙", 1400, 0, 3),
    )
    ratings = MappingProxyType(
        {
            competitor: item.new_rating
            for competitor, item in zip(competitors, changes, strict=True)
        }
    )
    result = SeriesRatingResult((ContestRatingResult(contest, changes, ratings),), ratings)

    document = project_series_rating_data(result, series_id="s", title="S")

    assert [item["rank"] for item in document["competitors"]] == [1, 1, 3]
    assert [item["id"] for item in document["competitors"][:2]] == sorted(
        stable_id(competitor) for competitor in competitors[:2]
    )


def test_sparse_participations_support_all_static_views() -> None:
    document = project_fixture()
    competitors = document["competitors"]
    assert isinstance(competitors, list)
    alice = next(item for item in competitors if item["member"] == "甲同学")
    bob = next(item for item in competitors if item["member"] == "乙")

    def wide_row(competitor: dict[str, object]) -> list[int | None]:
        states: list[int | None] = []
        rating: int | None = None
        by_contest = {
            participation["contestIndex"]: participation
            for participation in competitor["participations"]
        }
        for contest_index in range(2):
            participation = by_contest.get(contest_index)
            if participation is not None:
                rating = participation["after"]
            states.append(rating)
        return states

    assert wide_row(alice) == [1420, 1400]
    assert wide_row(bob) == [1400, 1400]
    second_contest = [
        participation
        for competitor in competitors
        for participation in competitor["participations"]
        if participation["contestIndex"] == 1
    ]
    assert second_contest == [
        {
            "contestIndex": 1,
            "contestRank": 1,
            "before": 1420,
            "delta": -20,
            "after": 1400,
        }
    ]
    assert [item["after"] for item in alice["participations"]] == [1420, 1400]


def test_projection_rejects_broken_rating_invariants() -> None:
    result, alice, bob = result_fixture()
    broken = change(alice, "测试大学", "甲", 1419, -19, 1)
    second = ContestRatingResult(
        result.contests[1].contest,
        (broken,),
        MappingProxyType({alice: 1400, bob: 1400}),
    )
    invalid = SeriesRatingResult((result.contests[0], second), result.ratings)
    with pytest.raises(DataValidationError, match="not continuous"):
        project_series_rating_data(invalid, series_id="s", title="S")


def test_atomic_json_write_is_compact_unicode_and_deterministic(tmp_path) -> None:
    path = tmp_path / "nested" / "data.json"
    document = {"中文": [1, 2], "value": 3}
    generate_static_data.write_json_atomic(path, document)
    first = path.read_bytes()
    generate_static_data.write_json_atomic(path, document)

    assert path.read_bytes() == first == b'{"\xe4\xb8\xad\xe6\x96\x87":[1,2],"value":3}\n'
    assert json.loads(path.read_text(encoding="utf-8")) == document
    assert not (path.parent / ".data.json.tmp").exists()


def test_generator_publishes_series_before_index(monkeypatch, tmp_path) -> None:
    result, _, _ = result_fixture()
    writes = []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(generate_static_data, "RankLandClient", Client)
    monkeypatch.setattr(
        generate_static_data,
        "load_2025_2026_season",
        lambda client: type("Season", (), {"contests": ()})(),
    )
    monkeypatch.setattr(generate_static_data, "calculate_series_ratings", lambda contests: result)
    original_write = generate_static_data.write_json_atomic

    def recording_write(path, document):
        writes.append(path.relative_to(tmp_path).as_posix())
        original_write(path, document)

    monkeypatch.setattr(generate_static_data, "write_json_atomic", recording_write)
    generate_static_data.generate_static_data(tmp_path)

    assert writes == ["series/2025-2026.json", "index.json"]
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))[
        "defaultSeriesId"
    ] == "2025-2026"
