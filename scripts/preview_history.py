"""Offline previous-season team history from local SRK snapshots."""

from __future__ import annotations

import argparse
import json
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from itertools import accumulate
from pathlib import Path

from core import DefaultNormalizer
from core.rankland import normalize_srk_contest


def _history_medals(payload: dict, teams: tuple, filename: str) -> dict:
    """Resolve explicit SRK count/ratio bands over the official standings."""
    options = next((entry["rule"].get("options", {})
                    for entry in payload.get("series", [])
                    if entry.get("rule", {}).get("preset") == "ICPC"), {})
    # The older xcpcrating cache has a zero placeholder. The existing xcpc-elo
    # srk-collection/official/icpc/icpc2025/icpc2025wuhan.srk.json supplies these
    # explicit counts. Keep the original standings and repair only this rule.
    if (filename == "icpc2025wuhan.srk.json" and "ratio" not in options
            and options.get("count", {}).get("value") == [0, 0, 0]):
        options = {**options, "count": {**options["count"], "value": [45, 90, 136]}}
    if options.get("filter"):
        raise ValueError(f"{filename}: unsupported medal filter")
    official = sorted((team for team in teams if team.official),
                      key=lambda team: (-team.solved, team.penalty))
    endpoints = []
    no_tied = False
    for kind in ("count", "ratio"):
        if kind not in options:
            continue
        rule = options[kind]
        values = rule.get("value")
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"{filename}: expected three nonnegative medal {kind}s")
        if any(type(v) not in (int, float) or not Decimal(str(v)).is_finite()
               or v < 0 or (kind == "count" and type(v) is not int) for v in values):
            raise ValueError(f"{filename}: expected three nonnegative medal {kind}s")
        if type(rule.get("noTied", False)) is not bool:
            raise ValueError(f"{filename}: medal noTied must be boolean")
        no_tied |= rule.get("noTied", False)
        if kind == "count":
            endpoints.append(list(accumulate(values)))
            continue
        if sum(Decimal(str(v)) for v in values) > 1:
            raise ValueError(f"{filename}: medal ratios must sum to at most one")
        denominator = rule.get("denominator", "all")
        rounding = rule.get("rounding", "ceil")
        rounders = {"ceil": ROUND_CEILING, "floor": ROUND_FLOOR, "round": ROUND_HALF_UP}
        if denominator not in ("all", "submitted", "scored") or rounding not in rounders:
            raise ValueError(f"{filename}: unsupported medal ratio denominator or rounding")
        submitted = {str(row["user"]["id"]) for row in payload["rows"]
                     if any(status.get("result") is not None for status in row.get("statuses", []))}
        total = sum(denominator == "all" or
                    (team.solved > 0 if denominator == "scored" else team.team_id in submitted)
                    for team in official)
        endpoints.append([int((v * total).to_integral_value(rounding=rounders[rounding]))
                          for v in accumulate(Decimal(str(v)) for v in values)])
    medals = {}
    tied_rank = 0
    previous = None
    for position, team in enumerate(official, 1):
        score = (team.solved, team.penalty)
        if score != previous:
            tied_rank = position
        previous = score
        rank = position if no_tied else tied_rank
        medals[team.team_id] = next((name for i, name in enumerate(("gold", "silver", "bronze"))
                                     if endpoints and all(rank <= e[i] for e in endpoints)), None)
    return medals


def build_history_index(series: dict, root: Path, normalizer: DefaultNormalizer) -> dict:
    """Index official, active entries; retain separate historical teams per contest."""
    files = {path.name: path for path in root.rglob("*.srk.json")}
    index: dict = {}
    for contest in series["contests"]:
        contest_id = contest["id"]
        # Like the reference awards view, show regional contests and finals.
        if "preliminary" in contest_id:
            continue
        filename = f"{contest_id}.srk.json"
        if filename not in files:
            raise ValueError(f"{root}: missing history snapshot {filename}")
        payload = json.loads(files[filename].read_text(encoding="utf-8"))
        normalized = normalize_srk_contest(
            payload, contest_uk=contest_id, series=contest["collection"],
        )
        medals = _history_medals(payload, normalized.teams, filename)
        for team in normalized.teams:
            if not team.official or not team.has_activity:
                continue
            record = {
                "contestId": contest_id, "contestTitle": contest["title"],
                "startAt": contest["startAt"], "teamId": team.team_id,
                "teamName": team.team_name, "rank": team.rank, "medal": medals[team.team_id],
            }
            school = normalizer.school(team.school_name)
            for member in set(team.members):
                key = (normalizer.member(member), school)
                index.setdefault(key, []).append(record)
    return index


def team_history(team: dict, index: dict, normalizer: DefaultNormalizer) -> list[dict]:
    """Merge a historical team once, counting distinct matched current members."""
    grouped: dict = {}
    school = normalizer.school(team["school"])
    members = {normalizer.member(member["name"]) for member in team["members"]}
    for member in sorted(members):
        for record in index.get((member, school), []):
            key = (record["contestId"], record["teamId"])
            entry, matched = grouped.setdefault(key, (record, set()))
            matched.add(member)
    return sorted(
        [{**record, "matchedMembers": len(matched)} for record, matched in grouped.values()],
        key=lambda record: (
            not record["contestId"].startswith("icpc"), record["startAt"],
            record["rank"], record["teamId"],
        ),
    )


def main() -> None:
    from scripts.generate_preview_data import load_normalizer, write_json_atomic

    parser = argparse.ArgumentParser(description="Add offline history to existing previews")
    parser.add_argument("--series", type=Path, required=True)
    parser.add_argument("--srk-root", type=Path, required=True)
    parser.add_argument("--preview", type=Path, action="append", required=True)
    args = parser.parse_args()
    normalizer = load_normalizer(Path(__file__).resolve().parents[1] / "config/school-aliases.json")
    series = json.loads(args.series.read_text(encoding="utf-8"))
    index = build_history_index(series, args.srk_root, normalizer)
    documents = []
    for path in args.preview:
        document = json.loads(path.read_text(encoding="utf-8"))
        year = int(document["seriesId"].split("-")[0])
        if series["id"] != f"{year - 1}-{year}":
            raise ValueError(f"{path}: history must come from the previous season")
        for team in document["teams"]:
            team["previousSeasonHistory"] = team_history(team, index, normalizer)
        documents.append((path, document))
    for path, document in documents:
        write_json_atomic(path, document)


if __name__ == "__main__":
    main()
