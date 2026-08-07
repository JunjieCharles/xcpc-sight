from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from core.errors import DataValidationError
from core.models import CompetitorId

from .models import SeriesRatingResult

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SCHEMA_VERSION = 1


def _competitor_id(competitor: CompetitorId) -> str:
    identity = f"{competitor.school}\0{competitor.member}".encode()
    return f"c_{hashlib.sha256(identity).hexdigest()}"


def _shanghai_isoformat(value: datetime) -> str:
    value = (
        value.replace(tzinfo=_SHANGHAI)
        if value.tzinfo is None
        else value.astimezone(_SHANGHAI)
    )
    return value.isoformat()


def project_series_rating_data(
    result: SeriesRatingResult,
    *,
    series_id: str,
    title: str,
    initial_rating: int = 1400,
) -> dict[str, object]:
    """Project a series rating result into the static-site JSON document."""
    if not result.contests:
        raise DataValidationError("published rating series must contain at least one contest")
    contests = []
    for contest_result in result.contests:
        contest = {
            "id": contest_result.contest.contest_id,
            "title": contest_result.contest.title,
            "collection": contest_result.contest.series,
            "startAt": _shanghai_isoformat(contest_result.contest.start_at),
        }
        if contest_result.contest.unrated_reason is not None:
            if not contest_result.contest.unrated_reason.strip():
                raise DataValidationError(
                    f"contest {contest_result.contest.contest_id}: "
                    "unrated reason must not be empty"
                )
            contest["rated"] = False
            contest["unratedReason"] = contest_result.contest.unrated_reason
        contests.append(contest)

    participations: dict[CompetitorId, list[dict[str, int]]] = {}
    displays: dict[CompetitorId, tuple[str, str]] = {}
    seen_ids: dict[str, CompetitorId] = {}
    for contest_index, contest_result in enumerate(result.contests):
        seen_in_contest: set[CompetitorId] = set()
        for change in contest_result.changes:
            competitor = change.competitor
            if contest_result.contest.unrated_reason is not None and (
                change.delta != 0 or change.old_rating != change.new_rating
            ):
                raise DataValidationError(
                    f"contest index {contest_index}, competitor {competitor}: "
                    "unrated contest must not change rating"
                )
            if competitor in seen_in_contest:
                raise DataValidationError(
                    f"contest index {contest_index}: duplicate competitor {competitor}"
                )
            seen_in_contest.add(competitor)
            if change.rank <= 0:
                raise DataValidationError(
                    f"contest index {contest_index}, competitor {competitor}: rank must be positive"
                )
            if change.old_rating + change.delta != change.new_rating:
                raise DataValidationError(
                    f"contest index {contest_index}, competitor {competitor}: "
                    "before + delta does not equal after"
                )
            history = participations.setdefault(competitor, [])
            if history and history[-1]["after"] != change.old_rating:
                raise DataValidationError(
                    f"contest index {contest_index}, competitor {competitor}: "
                    "rating is not continuous"
                )
            history.append(
                {
                    "contestIndex": contest_index,
                    "contestRank": change.rank,
                    "before": change.old_rating,
                    "delta": change.delta,
                    "after": change.new_rating,
                }
            )
            displays[competitor] = (change.display_school, change.display_member)

    if set(participations) != set(result.ratings):
        raise DataValidationError(
            "final ratings must contain exactly the competitors with participations"
        )

    projected: list[dict[str, object]] = []
    for competitor, history in participations.items():
        stable_id = _competitor_id(competitor)
        conflicting = seen_ids.get(stable_id)
        if conflicting is not None and conflicting != competitor:
            raise DataValidationError(
                f"stable competitor ID collision between {conflicting} and {competitor}"
            )
        seen_ids[stable_id] = competitor
        final_rating = result.ratings[competitor]
        if not history or history[-1]["after"] != final_rating:
            raise DataValidationError(
                f"competitor {competitor}: final participation does not match final rating"
            )
        if any(
            participation["contestIndex"] < 0
            or participation["contestIndex"] >= len(contests)
            for participation in history
        ):
            raise DataValidationError(f"competitor {competitor}: contest index out of range")
        if any(
            left["contestIndex"] >= right["contestIndex"]
            for left, right in zip(history, history[1:], strict=False)
        ):
            raise DataValidationError(
                f"competitor {competitor}: participations are not strictly ordered"
            )
        display_school, display_member = displays[competitor]
        projected.append(
            {
                "id": stable_id,
                "rank": 0,
                "school": display_school,
                "member": display_member,
                "finalRating": final_rating,
                "contestsParticipated": len(history),
                "participations": history,
            }
        )

    projected.sort(
        key=lambda item: (
            -int(item["finalRating"]),
            str(item["school"]),
            str(item["id"]),
        )
    )
    previous_rating: int | None = None
    current_rank = 0
    for position, competitor in enumerate(projected, start=1):
        final_rating = int(competitor["finalRating"])
        if final_rating != previous_rating:
            current_rank = position
            previous_rating = final_rating
        competitor["rank"] = current_rank

    return {
        "schemaVersion": _SCHEMA_VERSION,
        "id": series_id,
        "title": title,
        "initialRating": initial_rating,
        "contests": contests,
        "competitors": projected,
    }


def project_static_data_index(
    publications: Sequence[tuple[Mapping[str, object], str]] | None = None,
    *,
    series_id: str | None = None,
    title: str | None = None,
    path: str | None = None,
) -> Mapping[str, object]:
    """Build a newest-first index for published rating series documents."""
    if publications is None:
        if not series_id or not title or not path:
            raise DataValidationError(
                "provide publications or the legacy series_id, title, and path"
            )
        return {
            "schemaVersion": _SCHEMA_VERSION,
            "defaultSeriesId": series_id,
            "series": [{"id": series_id, "title": title, "path": path}],
        }
    if any(value is not None for value in (series_id, title, path)):
        raise DataValidationError(
            "publications cannot be combined with series_id, title, or path"
        )
    if not publications:
        raise DataValidationError("static data index must contain at least one series")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    entries: list[tuple[datetime, dict[str, str]]] = []
    for document, path in publications:
        series_id = document.get("id")
        title = document.get("title")
        contests = document.get("contests")
        if not isinstance(series_id, str) or not series_id:
            raise DataValidationError("series document id must be a non-empty string")
        if not isinstance(title, str) or not title:
            raise DataValidationError(f"series {series_id}: title must be a non-empty string")
        if not isinstance(path, str) or not path:
            raise DataValidationError(f"series {series_id}: path must be a non-empty string")
        if series_id in seen_ids:
            raise DataValidationError(f"duplicate series id {series_id!r}")
        if path in seen_paths:
            raise DataValidationError(f"duplicate series path {path!r}")
        if not isinstance(contests, list) or not contests:
            raise DataValidationError(
                f"series {series_id}: published series must contain at least one contest"
            )
        latest: datetime | None = None
        for contest_index, contest in enumerate(contests):
            if not isinstance(contest, Mapping):
                raise DataValidationError(
                    f"series {series_id}.contests[{contest_index}] must be an object"
                )
            start_at = contest.get("startAt")
            if not isinstance(start_at, str):
                raise DataValidationError(
                    f"series {series_id}.contests[{contest_index}].startAt must be a string"
                )
            try:
                parsed = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
            except ValueError as error:
                raise DataValidationError(
                    f"series {series_id}.contests[{contest_index}].startAt is invalid"
                ) from error
            if parsed.tzinfo is None:
                raise DataValidationError(
                    f"series {series_id}.contests[{contest_index}].startAt must have an offset"
                )
            latest = parsed if latest is None or parsed > latest else latest
        seen_ids.add(series_id)
        seen_paths.add(path)
        entries.append((latest, {"id": series_id, "title": title, "path": path}))

    entries.sort(key=lambda item: item[1]["id"])
    entries.sort(key=lambda item: item[0], reverse=True)
    series = [entry for _, entry in entries]
    return {
        "schemaVersion": _SCHEMA_VERSION,
        "defaultSeriesId": series[0]["id"],
        "series": series,
    }
