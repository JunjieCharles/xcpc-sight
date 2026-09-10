"""Offline previous-season team history from local SRK snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import DefaultNormalizer
from core.rankland import normalize_srk_contest


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
        # Only explicit SRK award counts are used. Ratio rules are not award evidence.
        counts = []
        for rule in payload.get("series", []):
            if rule.get("rule", {}).get("preset") == "ICPC":
                counts = rule["rule"].get("options", {}).get("count", {}).get("value", [])
                break
        if counts and (len(counts) != 3 or any(type(n) is not int or n < 0 for n in counts)):
            raise ValueError(f"{filename}: expected three nonnegative medal counts")
        for team in normalized.teams:
            if not team.official or not team.has_activity:
                continue
            medal = None
            cutoff = 0
            for name, count in zip(("gold", "silver", "bronze"), counts, strict=False):
                cutoff += count
                if team.rank <= cutoff:
                    medal = name
                    break
            record = {
                "contestId": contest_id, "contestTitle": contest["title"],
                "startAt": contest["startAt"], "teamId": team.team_id,
                "teamName": team.team_name, "rank": team.rank, "medal": medal,
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
