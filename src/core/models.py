from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True, order=True)
class CompetitorId:
    school: str
    member: str


@dataclass(frozen=True, slots=True)
class TeamResult:
    team_id: str
    team_name: str
    school_name: str
    members: tuple[str, ...]
    rank: int
    solved: int
    penalty: int
    official: bool = True
    has_activity: bool = True


@dataclass(frozen=True, slots=True)
class ContestProvenance:
    contest_uk: str
    file_id: str
    file_url: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class Contest:
    contest_id: str
    title: str
    series: str
    start_at: datetime
    teams: tuple[TeamResult, ...]
    provenance: ContestProvenance | None = None


@dataclass(frozen=True, slots=True)
class SeasonDecision:
    contest_id: str
    title: str
    included: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SeasonData:
    name: str
    contests: tuple[Contest, ...]
    decisions: tuple[SeasonDecision, ...] = field(default_factory=tuple)
