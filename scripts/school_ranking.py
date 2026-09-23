"""Pure school rankings and representative team histories for video cards."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf

from core import Contest, DefaultNormalizer, TeamResult, rebuild_competition_ranks


@dataclass(frozen=True)
class TeamStanding:
    name: str
    members: tuple[str, ...]
    ranks: tuple[int | None, ...]


@dataclass(frozen=True)
class SchoolStanding:
    rank: int
    school: str
    ranks: tuple[int | None, ...]
    teams: tuple[TeamStanding, ...]


def rank_key(ranks: tuple[int | None, ...]) -> tuple[float, ...]:
    """Best result first; a missing result loses to any real rank."""
    return tuple(sorted(inf if rank is None else rank for rank in ranks))


def school_standings(
    contests: tuple[Contest, ...], normalizer: DefaultNormalizer,
) -> tuple[SchoolStanding, ...]:
    """Competition ranks, with one best official active result per school.

    Team histories join only identical normalized member sets within a school.
    An empty member set uses a contest-local identity rather than guessing.
    """
    if not contests or len({c.contest_id for c in contests}) != len(contests):
        raise ValueError("contests must be nonempty and have unique IDs")
    school_names: dict[str, str] = {}
    school_ranks: dict[str, list[int | None]] = {}
    histories: dict[tuple[str, tuple[str, ...]], list[int | None]] = {}
    displays: dict[tuple[str, tuple[str, ...]], TeamResult] = {}
    representatives: set[tuple[str, tuple[str, ...]]] = set()
    top_teams: set[tuple[str, tuple[str, ...]]] = set()
    for index, contest in enumerate(contests):
        teams = rebuild_competition_ranks(contest.teams, contest_id=contest.contest_id)
        active = [t for t in teams if t.official and t.has_activity]
        best: dict[str, int] = {}
        for team in active:
            school = normalizer.school(team.school_name)
            school_names[school] = team.school_name
            best[school] = min(best.get(school, team.rank), team.rank)
        ordered = sorted(best, key=lambda s: (best[s], s))
        school_rank = 0
        for position, school in enumerate(ordered):
            if position == 0 or best[school] != best[ordered[position - 1]]:
                school_rank = position + 1
            school_ranks.setdefault(school, [None] * len(contests))[index] = school_rank
        for team in sorted(active, key=lambda t: (t.rank, t.team_id)):
            school = normalizer.school(team.school_name)
            members = tuple(sorted({normalizer.member(m) for m in team.members}))
            identity = (school, members or (f"{contest.contest_id}:{team.team_id}",))
            history = histories.setdefault(identity, [None] * len(contests))
            if history[index] is None or team.rank < history[index]:
                history[index] = team.rank
                displays[identity] = team
            if team.rank == best[school]:
                representatives.add(identity)
            if team.rank <= 100:
                top_teams.add(identity)
    ordered_schools = sorted(school_ranks, key=lambda s: (rank_key(tuple(school_ranks[s])), s))
    result = []
    rank = 0
    previous = None
    for position, school in enumerate(ordered_schools):
        ranks = tuple(school_ranks[school])
        key = rank_key(ranks)
        if key != previous:
            rank = position + 1
        previous = key
        candidates = {identity for identity in top_teams if identity[0] == school}
        if not candidates:
            candidates = {identity for identity in representatives if identity[0] == school}
        selected = sorted(
            candidates,
            key=lambda identity: (rank_key(tuple(histories[identity])), identity),
        )
        result.append(SchoolStanding(
            rank, school_names[school], ranks,
            tuple(TeamStanding(displays[i].team_name, displays[i].members, tuple(histories[i]))
                  for i in selected),
        ))
    return tuple(result)
