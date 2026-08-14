from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
        ((document, "series/2025-2026.json"),)
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
    assert [item["school"] for item in competitors] == sorted(
        item["school"] for item in competitors
    )
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


def test_index_sorts_by_latest_contest_then_series_id() -> None:
    older = project_fixture()
    older["id"] = "z-series"
    older["title"] = "Older"
    newer = project_fixture()
    newer["id"] = "b-series"
    newer["title"] = "Newer"
    newer["contests"][0]["startAt"] = "2026-07-24T12:00:00+08:00"
    tie = project_fixture()
    tie["id"] = "a-series"
    tie["title"] = "Tie"
    tie["contests"][1]["startAt"] = "2026-07-24T12:00:00+08:00"

    index = project_static_data_index(
        (
            (older, "series/z.json"),
            (newer, "series/b.json"),
            (tie, "series/a.json"),
        )
    )

    assert [item["id"] for item in index["series"]] == [
        "a-series",
        "b-series",
        "z-series",
    ]
    assert index["defaultSeriesId"] == "a-series"


def test_published_index_matches_published_series_documents() -> None:
    data_dir = Path(__file__).parents[1] / "static" / "data"
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    publications = tuple(
        (
            json.loads((data_dir / entry["path"]).read_text(encoding="utf-8")),
            entry["path"],
        )
        for entry in index["series"]
    )

    assert index == project_static_data_index(publications)


def test_index_and_series_reject_empty_or_duplicate_publications() -> None:
    empty_result = SeriesRatingResult((), MappingProxyType({}))
    with pytest.raises(DataValidationError, match="at least one contest"):
        project_series_rating_data(empty_result, series_id="empty", title="Empty")
    with pytest.raises(DataValidationError, match="at least one series"):
        project_static_data_index(())

    document = project_fixture()
    duplicate = dict(document)
    with pytest.raises(DataValidationError, match="duplicate series id"):
        project_static_data_index(
            ((document, "series/a.json"), (duplicate, "series/b.json"))
        )
    duplicate["id"] = "other"
    with pytest.raises(DataValidationError, match="duplicate series path"):
        project_static_data_index(
            ((document, "series/a.json"), (duplicate, "series/a.json"))
        )


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


def test_projection_sorts_equal_ratings_by_school_before_stable_id() -> None:
    zeta = CompetitorId("zeta", "member")
    alpha = CompetitorId("alpha", "member")
    contest = Contest("only", "Only", "series", datetime(2025, 10, 1, 9), ())
    changes = (
        change(zeta, "Zeta University", "Zeta", 1400, 100, 1),
        change(alpha, "Alpha University", "Alpha", 1400, 100, 1),
    )
    ratings = MappingProxyType(
        {
            competitor: item.new_rating
            for competitor, item in zip((zeta, alpha), changes, strict=True)
        }
    )
    result = SeriesRatingResult((ContestRatingResult(contest, changes, ratings),), ratings)

    document = project_series_rating_data(result, series_id="s", title="S")

    assert [item["school"] for item in document["competitors"]] == [
        "Alpha University",
        "Zeta University",
    ]


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


def test_generator_registers_fixed_hdu_contests(monkeypatch) -> None:
    requested: list[int] = []

    class FakeHduClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def fetch_contest(self, contest_id):
            requested.append(contest_id)
            return Contest(
                f"hdu:{contest_id}",
                f"HDU {contest_id}",
                "hdu-summer-2026",
                datetime(2026, 7, 1, tzinfo=UTC)
                + timedelta(days=contest_id - 1229),
                (),
            )

    monkeypatch.setattr(generate_static_data, "HduClient", FakeHduClient)

    contests = generate_static_data.load_hdu_series()

    assert requested == [1229, 1230, 1231, 1232, 1233, 1234, 1235, 1236]
    assert [contest.contest_id for contest in contests] == [
        "hdu:1229",
        "hdu:1230",
        "hdu:1231",
        "hdu:1232",
        "hdu:1233",
        "hdu:1234",
        "hdu:1235",
        "hdu:1236",
    ]
    assert all(contest.unrated_reason is None for contest in contests)
    hdu_spec = next(
        spec for spec in generate_static_data.series_specs() if spec.series_id == "hdu-summer-2026"
    )
    assert hdu_spec.path == "series/hdu-summer-2026.json"


def test_projection_marks_unrated_contest_and_preserves_zero_delta_rank() -> None:
    competitor = CompetitorId("大学", "甲")
    unrated = Contest(
        "unrated",
        "故障场",
        "series",
        datetime(2026, 8, 6, tzinfo=UTC),
        (),
        unrated_reason="checker挂了",
    )
    unchanged = change(competitor, "大学", "甲", 1500, 0, 7)
    ratings = MappingProxyType({competitor: 1500})
    result = SeriesRatingResult(
        (ContestRatingResult(unrated, (unchanged,), ratings),), ratings
    )

    document = project_series_rating_data(result, series_id="series", title="Series")

    assert document["contests"][0]["rated"] is False
    assert document["contests"][0]["unratedReason"] == "checker挂了"
    assert document["competitors"][0]["participations"][0] == {
        "contestIndex": 0,
        "contestRank": 7,
        "before": 1500,
        "delta": 0,
        "after": 1500,
    }


def test_generator_registers_nine_nowcoder_contests(monkeypatch) -> None:
    requested: list[int] = []

    class FakeNowcoderClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def fetch_leaderboard(self, contest_id):
            requested.append(contest_id)
            return contest_id

    def to_contest(contest_id, *, title):
        return Contest(
            f"nowcoder:{contest_id}",
            title,
            "nowcoder-summer-2026",
            datetime(2026, 7, contest_id - 133870, tzinfo=UTC),
            (),
        )

    monkeypatch.setattr(generate_static_data, "NowcoderClient", FakeNowcoderClient)
    monkeypatch.setattr(generate_static_data, "nowcoder_leaderboard_to_contest", to_contest)

    contests = generate_static_data.load_nowcoder_series()

    assert requested == [
        133876,
        133877,
        133878,
        133879,
        133880,
        133881,
        133882,
        133883,
        133884,
    ]
    assert [contest.contest_id for contest in contests] == [
        "nowcoder:133876",
        "nowcoder:133877",
        "nowcoder:133878",
        "nowcoder:133879",
        "nowcoder:133880",
        "nowcoder:133881",
        "nowcoder:133882",
        "nowcoder:133883",
        "nowcoder:133884",
    ]


def test_generator_publishes_all_series_before_index(monkeypatch, tmp_path) -> None:
    result, _, _ = result_fixture()
    writes = []
    loads = []

    def load_named(name):
        def load():
            loads.append(name)
            return result.contests

        return load

    monkeypatch.setattr(
        generate_static_data,
        "series_specs",
        lambda: (
            generate_static_data.SeriesSpec("old", "Old", "series/old.json", load_named("old")),
            generate_static_data.SeriesSpec(
                "middle", "Middle", "series/middle.json", load_named("middle")
            ),
            generate_static_data.SeriesSpec("new", "New", "series/new.json", load_named("new")),
        ),
    )
    monkeypatch.setattr(generate_static_data, "calculate_series_ratings", lambda contests: result)
    original_write = generate_static_data.write_json_atomic

    def recording_write(path, document):
        assert loads == ["old", "middle", "new"]
        writes.append(path.relative_to(tmp_path).as_posix())
        original_write(path, document)

    monkeypatch.setattr(generate_static_data, "write_json_atomic", recording_write)
    generate_static_data.generate_static_data(tmp_path)

    assert writes == [
        "series/old.json",
        "series/middle.json",
        "series/new.json",
        "index.json",
    ]
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["defaultSeriesId"] == "middle"
