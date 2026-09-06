"""Pure projection of team results onto an unchanged pre-contest roster."""

import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import DataValidationError
from .models import Contest
from .normalization import DefaultNormalizer
from .ranking import rebuild_competition_ranks


def _team_name(value: str) -> str:
    # Team names may consist entirely of punctuation; never normalize as a person.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def project_review_contest(
    preview: Mapping[str, Any],
    contest: Contest,
    *,
    normalizer: DefaultNormalizer | None = None,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Match each preview team exactly once; overrides map preview IDs to result IDs."""
    normalizer = normalizer or DefaultNormalizer()
    overrides = overrides or {}
    results = [
        team
        for team in rebuild_competition_ranks(contest.teams, contest_id=contest.contest_id)
        if team.official
    ]
    by_id = {team.team_id: team for team in results}
    if len(by_id) != len(results):
        raise DataValidationError(f"contest {contest.contest_id}: duplicate result team ID")
    names = defaultdict(list)
    members = defaultdict(list)
    for team in results:
        school = normalizer.school(team.school_name)
        names[(school, _team_name(team.team_name))].append(team)
        members[(school, tuple(sorted(normalizer.member(n) for n in team.members)))].append(team)
    roster = preview["teams"]
    roster_ids = {team["id"] for team in roster}
    if len(roster_ids) != len(roster):
        raise DataValidationError(f"preview {preview['id']}: duplicate team ID")
    if set(overrides) - roster_ids:
        raise DataValidationError(f"contest {contest.contest_id}: unknown override preview IDs")
    used = set()
    rows = []
    for team in roster:
        school = normalizer.school(team["school"])
        candidates = names[(school, _team_name(team["name"]))]
        if len(candidates) != 1:
            candidates = members[
                (
                    school,
                    tuple(sorted(normalizer.member(member["name"]) for member in team["members"])),
                )
            ]
        if team["id"] in overrides:
            target = by_id.get(overrides[team["id"]])
            candidates = [target] if target else []
        if len(candidates) != 1 or candidates[0].team_id in used:
            raise DataValidationError(
                f"contest {contest.contest_id}, preview team {team['id']} "
                f"({team['school']} / {team['name']}): expected unique unused result; "
                f"candidates={[candidate.team_id for candidate in candidates]}"
            )
        result = candidates[0]
        used.add(result.team_id)
        rows.append(
            {
                "previewTeamId": team["id"],
                "resultTeamId": result.team_id,
                "hasActivity": result.has_activity,
                "actualRank": result.rank if result.has_activity else None,
            }
        )
    source = {"title": "RankLand", "url": f"https://rl.algoux.cn/ranklist/{contest.contest_id}"}
    if contest.provenance:
        source.update(
            {
                "fileId": contest.provenance.file_id,
                "fileUrl": contest.provenance.file_url,
                "sha256": contest.provenance.sha256,
            }
        )
    return {
        "id": contest.contest_id,
        "previewId": preview["id"],
        "title": contest.title,
        "startAt": contest.start_at.isoformat(),
        "source": source,
        "teams": rows,
    }
