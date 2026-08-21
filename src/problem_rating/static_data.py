from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.errors import DataValidationError

SCHEMA_VERSION = 1
MODEL_ID = "gaussian-prev1-3-shallow-gbr-no-order"
_MISSING_PROBLEM_NAMES = frozenset(
    {
        "官方 guest 数据未提供题名",
        "RankLand 公开榜单未提供题名",
    }
)
_CONTEST_SHORT_TITLES = {
    "2025-2026": {
        "icpc2025preliminary-1": "ICPC 网络赛1",
        "icpc2025preliminary-2": "ICPC 网络赛2",
        "ccpc2025preliminary": "CCPC 网络赛",
        "icpc2025xi_an": "ICPC 西安",
        "icpc2025chengdu": "ICPC 成都",
        "icpc2025wuhan": "ICPC 武汉",
        "ccpc2025harbin": "CCPC 哈尔滨",
        "icpc2025nanjing": "ICPC 南京",
        "ccpc2025jinan": "CCPC 济南",
        "icpc2025shenyang": "ICPC 沈阳",
        "ccpc2025zhengzhou": "CCPC 郑州",
        "icpc2025shanghai": "ICPC 上海",
        "ccpc2025chongqing": "CCPC 重庆",
        "icpc2025hongkong": "ICPC 香港",
        "icpc2025ecfinal": "ICPC EC-Final",
        "ccpc2025final": "CCPC 总决赛",
    }
}


@dataclass(frozen=True, slots=True)
class ProblemRatingRecord:
    """One problem-level prediction before static-site projection."""

    series_id: str
    native_contest_id: str
    contest_name: str
    problem_index: str
    problem_name: str
    solved_count: int
    participant_count: int
    time_sample_count: int
    predicted_rating: int

    def __post_init__(self) -> None:
        context = (
            f"series {self.series_id!r}, contest {self.native_contest_id!r}, "
            f"problem {self.problem_index!r}"
        )
        for field_name, value in (
            ("series_id", self.series_id),
            ("native_contest_id", self.native_contest_id),
            ("contest_name", self.contest_name),
            ("problem_index", self.problem_index),
            ("problem_name", self.problem_name),
        ):
            if not isinstance(value, str) or not value.strip():
                raise DataValidationError(f"{context}: {field_name} must be non-empty")
        for field_name, value in (
            ("solved_count", self.solved_count),
            ("participant_count", self.participant_count),
            ("time_sample_count", self.time_sample_count),
            ("predicted_rating", self.predicted_rating),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DataValidationError(f"{context}: {field_name} must be a non-negative integer")
        if self.solved_count > self.participant_count:
            raise DataValidationError(f"{context}: solved_count exceeds participant_count")
        if self.time_sample_count > self.solved_count:
            raise DataValidationError(f"{context}: time_sample_count exceeds solved_count")


def problem_index_sort_key(value: str) -> tuple[tuple[int, int | str], ...]:
    """Return a deterministic natural-sort key for indexes such as A2 and 1003."""
    parts = re.findall(r"\d+|\D+", value.casefold())
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def _required_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{context} must be a non-empty string")
    return value


def project_problem_rating_series(
    records: Sequence[ProblemRatingRecord],
    rating_series: Mapping[str, object],
) -> dict[str, object]:
    """Project predictions against one canonical participant-rating series."""
    series_id = _required_text(rating_series.get("id"), "rating series id")
    title = _required_text(rating_series.get("title"), f"series {series_id}: title")
    raw_contests = rating_series.get("contests")
    if not isinstance(raw_contests, list) or not raw_contests:
        raise DataValidationError(f"series {series_id}: contests must be a non-empty list")
    if not records:
        raise DataValidationError(f"series {series_id}: problem ratings must not be empty")

    by_native_id: dict[str, list[ProblemRatingRecord]] = {}
    seen_problems: set[tuple[str, str]] = set()
    for record in records:
        if record.series_id != series_id:
            raise DataValidationError(
                f"series {series_id}: received record for series {record.series_id!r}"
            )
        identity = (record.native_contest_id, record.problem_index)
        if identity in seen_problems:
            raise DataValidationError(
                f"series {series_id}, contest {record.native_contest_id}, "
                f"problem {record.problem_index}: duplicate record"
            )
        seen_problems.add(identity)
        by_native_id.setdefault(record.native_contest_id, []).append(record)

    contests: list[dict[str, object]] = []
    seen_contest_ids: set[str] = set()
    consumed_native_ids: set[str] = set()
    for contest_index, raw_contest in enumerate(raw_contests):
        context = f"series {series_id}.contests[{contest_index}]"
        if not isinstance(raw_contest, Mapping):
            raise DataValidationError(f"{context} must be an object")
        contest_id = _required_text(raw_contest.get("id"), f"{context}.id")
        contest_title = _required_text(raw_contest.get("title"), f"{context}.title")
        start_at = _required_text(raw_contest.get("startAt"), f"{context}.startAt")
        if contest_id in seen_contest_ids:
            raise DataValidationError(f"{context}.id duplicates {contest_id!r}")
        seen_contest_ids.add(contest_id)
        _, separator, namespaced_native_id = contest_id.partition(":")
        native_contest_id = namespaced_native_id if separator else contest_id
        contest_records = by_native_id.get(native_contest_id)
        if not contest_records:
            raise DataValidationError(
                f"{context}: no problem ratings for native contest {native_contest_id}"
            )
        consumed_native_ids.add(native_contest_id)
        contest_records.sort(key=lambda item: problem_index_sort_key(item.problem_index))
        problems = [
            {
                "index": record.problem_index,
                "name": (
                    "" if record.problem_name in _MISSING_PROBLEM_NAMES else record.problem_name
                ),
                "rating": record.predicted_rating,
                "solvedCount": record.solved_count,
                "participantCount": record.participant_count,
                "timeSampleCount": record.time_sample_count,
            }
            for record in contest_records
        ]
        projected_contest: dict[str, object] = {
            "id": contest_id,
            "title": contest_title,
            "startAt": start_at,
            "problems": problems,
        }
        short_title = _CONTEST_SHORT_TITLES.get(series_id, {}).get(contest_id)
        if short_title:
            projected_contest["shortTitle"] = short_title
        contests.append(projected_contest)

    extras = sorted(set(by_native_id) - consumed_native_ids)
    if extras:
        raise DataValidationError(
            f"series {series_id}: predictions reference unknown contests {extras}"
        )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "seriesId": series_id,
        "title": title,
        "modelId": MODEL_ID,
        "contests": contests,
    }


def project_problem_rating_index(
    publications: Sequence[tuple[Mapping[str, object], str]],
) -> dict[str, object]:
    """Build the index for independently published problem-rating series."""
    if not publications:
        raise DataValidationError("problem rating index must contain at least one series")
    series: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for document, path in publications:
        series_id = _required_text(document.get("seriesId"), "problem rating series id")
        title = _required_text(document.get("title"), f"series {series_id}: title")
        path = _required_text(path, f"series {series_id}: path")
        if series_id in seen_ids:
            raise DataValidationError(f"duplicate problem rating series id {series_id!r}")
        if path in seen_paths:
            raise DataValidationError(f"duplicate problem rating series path {path!r}")
        seen_ids.add(series_id)
        seen_paths.add(path)
        series.append({"id": series_id, "title": title, "path": path})
    return {"schemaVersion": SCHEMA_VERSION, "series": series}
