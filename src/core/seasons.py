from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import Contest, SeasonData, SeasonDecision
from .rankland import RankLandClient

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_INVITATIONAL = re.compile(r"邀请赛|invitational", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SeasonSpec:
    name: str
    collection_ids: tuple[str, ...]
    include_ids: frozenset[str] = frozenset()
    exclude_ids: frozenset[str] = frozenset()


SEASON_2025_2026 = SeasonSpec(
    name="2025-2026",
    collection_ids=("icpc2025", "ccpc2025"),
)


def _searchable_title(contest: Contest) -> str:
    return unicodedata.normalize("NFKC", contest.title).casefold()


def _is_invitational(contest: Contest) -> bool:
    return _INVITATIONAL.search(_searchable_title(contest)) is not None


def _local_start(start_at: datetime) -> datetime:
    if start_at.tzinfo is None:
        return start_at.replace(tzinfo=_SHANGHAI)
    return start_at.astimezone(_SHANGHAI)


def contest_sort_key(contest: Contest) -> tuple[object, ...]:
    local_start = _local_start(contest.start_at)
    series_priority = 0 if contest.series.casefold().startswith("ccpc") else 1
    return (
        local_start.date(),
        series_priority,
        local_start,
        _searchable_title(contest),
        contest.contest_id,
    )


def select_season(
    contests: tuple[Contest, ...],
    spec: SeasonSpec = SEASON_2025_2026,
) -> SeasonData:
    selected: list[Contest] = []
    decisions: list[SeasonDecision] = []
    allowed_series = set(spec.collection_ids)
    for contest in contests:
        included = False
        reason: str
        if contest.contest_id in spec.exclude_ids:
            reason = "explicitly excluded"
        elif contest.contest_id in spec.include_ids:
            included = True
            reason = "explicitly included"
        elif contest.series not in allowed_series:
            reason = f"not in season collections: {contest.series}"
        elif _is_invitational(contest):
            reason = "invitational excluded"
        else:
            included = True
            reason = "official collection member and not invitational"
        decisions.append(
            SeasonDecision(contest.contest_id, contest.title, included, reason)
        )
        if included:
            selected.append(contest)
    selected.sort(key=contest_sort_key)
    return SeasonData(spec.name, tuple(selected), tuple(decisions))


def load_season(client: RankLandClient, spec: SeasonSpec) -> SeasonData:
    return select_season(client.fetch_collections(spec.collection_ids), spec)


def load_2025_2026_season(client: RankLandClient) -> SeasonData:
    return load_season(client, SEASON_2025_2026)
