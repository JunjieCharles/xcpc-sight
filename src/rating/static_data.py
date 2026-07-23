from __future__ import annotations

import hashlib
from collections.abc import Mapping
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
    contests = [
        {
            "id": contest_result.contest.contest_id,
            "title": contest_result.contest.title,
            "collection": contest_result.contest.series,
            "startAt": _shanghai_isoformat(contest_result.contest.start_at),
        }
        for contest_result in result.contests
    ]

    participations: dict[CompetitorId, list[dict[str, int]]] = {}
    displays: dict[CompetitorId, tuple[str, str]] = {}
    seen_ids: dict[str, CompetitorId] = {}
    for contest_index, contest_result in enumerate(result.contests):
        seen_in_contest: set[CompetitorId] = set()
        for change in contest_result.changes:
            competitor = change.competitor
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

    projected.sort(key=lambda item: (-int(item["finalRating"]), str(item["id"])))
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
    *,
    series_id: str,
    title: str,
    path: str,
) -> Mapping[str, object]:
    """Build the static-site index for a single published rating series."""
    return {
        "schemaVersion": _SCHEMA_VERSION,
        "defaultSeriesId": series_id,
        "series": [{"id": series_id, "title": title, "path": path}],
    }
