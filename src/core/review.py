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
    removed_results: Mapping[str, str] | None = None,
    unofficial_results: Mapping[str, str] | None = None,
    result_medals: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    """Match results, optional medal labels, and explicit removed/unofficial mappings.

    result_medals covers exactly the official result IDs with gold/silver/bronze
    or None. Removed and unofficial rows preserve the original preview roster but
    have null activity/rank and do not enter analysis cohorts.
    """
    normalizer = normalizer or DefaultNormalizer()
    overrides = overrides or {}
    removed_results = {} if removed_results is None else removed_results
    unofficial_results = {} if unofficial_results is None else unofficial_results
    if not isinstance(removed_results, Mapping):
        raise DataValidationError("removed_results must map preview IDs to old result IDs")
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
    roster = [team for team in preview["teams"] if not team.get("excluded", False)]
    roster_ids = {team["id"] for team in roster}
    if not isinstance(unofficial_results, Mapping):
        raise DataValidationError("unofficial_results must map preview IDs to result IDs")
    if set(unofficial_results) - roster_ids:
        raise DataValidationError("unknown unofficial preview IDs")
    if set(unofficial_results) & (set(overrides) | set(removed_results)):
        raise DataValidationError("unofficial_results must not overlap other mappings")
    unofficial_by_id = {team.team_id: team for team in contest.teams if not team.official}
    if any(not isinstance(value, str) or value not in unofficial_by_id
           for value in unofficial_results.values()):
        raise DataValidationError("unofficial_results must reference current unofficial results")
    if len(set(unofficial_results.values())) != len(unofficial_results):
        raise DataValidationError("duplicate unofficial result IDs")
    if result_medals is not None:
        if not isinstance(result_medals, Mapping) or set(result_medals) != set(by_id):
            raise DataValidationError("result_medals must cover exactly all official result IDs")
        if any(value not in (None, "gold", "silver", "bronze")
               for value in result_medals.values()):
            raise DataValidationError("invalid result medal")
        if any(result_medals[t.team_id] is not None and not t.has_activity for t in results):
            raise DataValidationError("inactive results cannot receive medals")
    if len(roster_ids) != len(roster):
        raise DataValidationError(f"preview {preview['id']}: duplicate team ID")
    if set(overrides) - roster_ids:
        raise DataValidationError(f"contest {contest.contest_id}: unknown override preview IDs")
    if set(removed_results) - roster_ids:
        raise DataValidationError(f"contest {contest.contest_id}: unknown removed preview IDs")
    if set(removed_results) & set(overrides):
        raise DataValidationError("removed_results and overrides must not overlap")
    old_ids = list(removed_results.values())
    if any(not isinstance(value, str) or not value.strip() for value in old_ids):
        raise DataValidationError("removed_results requires nonempty string result IDs")
    if len(set(old_ids)) != len(old_ids):
        raise DataValidationError("removed_results contains duplicate old result IDs")
    if set(old_ids) & {team.team_id for team in contest.teams}:
        raise DataValidationError("removed_results references a result still present")
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
        if team["id"] in unofficial_results:
            if candidates:
                raise DataValidationError("unofficial result still matches an official result")
            rows.append({
                "previewTeamId": team["id"],
                "resultTeamId": unofficial_results[team["id"]],
                "resultStatus": "unofficial", "hasActivity": None, "actualRank": None,
                **({"actualMedal": None} if result_medals is not None else {}),
            })
            continue
        if team["id"] in removed_results:
            if candidates or names[(school, _team_name(team["name"]))]:
                raise DataValidationError(
                    f"preview team {team['id']}: removed result still matches current results"
                )
            rows.append({
                "previewTeamId": team["id"],
                "resultTeamId": removed_results[team["id"]],
                "resultStatus": "removed",
                "hasActivity": None,
                "actualRank": None,
                **({"actualMedal": None} if result_medals is not None else {}),
            })
            continue
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
                **({"actualMedal": result_medals[result.team_id]}
                   if result_medals is not None else {}),
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
        **({"hasMedals": True} if result_medals is not None else {}),
    }
