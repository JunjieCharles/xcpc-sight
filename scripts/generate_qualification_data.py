"""Explicit, offline publication of qualification standings from pinned SRK files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core.normalization import DefaultNormalizer
from core.rankland import normalize_srk_contest
from core.school_aliases import load_school_aliases
from scripts.generate_static_data import write_json_atomic

ROOT = Path(__file__).resolve().parents[1]


def project_station(
    spec: dict, payload: dict, normalizer: DefaultNormalizer, *, ccpcf: bool = False,
) -> dict:
    """Project official results without ratings or submission/account details."""
    contest = normalize_srk_contest(
        payload, contest_uk=spec["id"], series="ccpc2026" if ccpcf else "icpc2026",
    )
    official = [team for team in contest.teams if team.official]
    teams = []
    for team in sorted(official, key=lambda t: (t.rank, t.team_id)):
        school_key = normalizer.school(team.school_name)
        members = sorted(normalizer.member(member) for member in team.members)
        if not members or len(members) > 3 or len(set(members)) != len(members):
            raise ValueError(f"{spec['id']}/{team.team_id}: invalid contestant list")
        complete = len(members) == 3
        identity_parts = (
            [school_key, members] if complete and not ccpcf else [spec["id"], team.team_id]
        )
        identity = json.dumps(identity_parts, ensure_ascii=False, separators=(",", ":"))
        teams.append({
            "key": hashlib.sha256(identity.encode()).hexdigest(),
            "schoolKey": school_key,
            "school": team.school_name,
            "name": team.team_name,
            "members": list(team.members),
            "identityComplete": complete,
            "rank": team.rank,
            "solved": team.solved,
        })
        if ccpcf:
            teams[-1]["memberKeys"] = members
    if len({team["key"] for team in teams}) != len(teams):
        raise ValueError(f"{spec['id']}: duplicate team identity within station")
    return {
        **spec, "status": "finished", "date": contest.start_at.date().isoformat(),
        "officialCount": len(official),
        "effectiveCount": sum(team.solved > 0 for team in official),
        "teams": teams,
    }


def build_document(config: dict, input_dirs: list[Path], review: dict, aliases: dict,
                   *, previews: dict | None = None) -> dict:
    sources = {contest["id"]: contest["source"] for contest in review["contests"]}
    normalizer = DefaultNormalizer(school_aliases=aliases)
    stations = []
    for spec in config["stations"]:
        if spec["status"] == "pending":
            station = {**spec, "teams": []}
            if preview_id := spec.get("previewId"):
                preview = (previews or {}).get(preview_id)
                if not preview or (preview["id"], preview["seriesId"]) != (
                    preview_id, config["seriesId"]
                ):
                    raise ValueError(f"{spec['id']}: missing or mismatched preview {preview_id}")
                station["previewIdentities"] = {
                    t["id"]: {
                        "schoolKey": normalizer.school(t["school"]),
                        "memberKeys": sorted(normalizer.member(m["name"]) for m in t["members"]),
                    }
                    for t in preview["teams"] if not t["excluded"]
                }
            stations.append(station)
            continue
        if spec["id"] not in sources:
            raise ValueError(f"{spec['id']}: no pinned source in published review")
        source = sources[spec["id"]]
        files = [directory / f"{spec['id']}.srk.json" for directory in input_dirs]
        path = next((path for path in files if path.is_file()), None)
        if path is None:
            raise ValueError(f"{spec['id']}: pinned SRK not found in input directories")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"{path}: SHA-256 does not match published review")
        station = project_station(
            spec, json.loads(data), normalizer, ccpcf=config.get("kind") == "ccpcf",
        )
        station["source"] = source
        stations.append(station)
    return {**config, "stations": stations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config/qualification-2026-2027.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "static/data")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    review = json.loads((ROOT / "static/data/reviews/2026-2027.json").read_text(encoding="utf-8"))
    previews = {
        pid: json.loads((ROOT / f"static/data/previews/{pid}.json").read_text(encoding="utf-8"))
        for s in config["stations"] if s["status"] == "pending" and (pid := s.get("previewId"))
    }
    document = build_document(
        config, args.input_dir, review, load_school_aliases(ROOT / "config/school-aliases.json"),
        previews=previews,
    )
    ccpcf = document.get("kind") == "ccpcf"
    path = f"qualification/{'ccpcf-' if ccpcf else ''}{document['seriesId']}.json"
    index_path = args.output_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
    if index:
        entry = next(entry for entry in index["series"] if entry["id"] == document["seriesId"])
        entry["ccpcfQualificationPath" if ccpcf else "qualificationPath"] = path
    write_json_atomic(args.output_dir / path, document)
    if index:
        write_json_atomic(index_path, index)


if __name__ == "__main__":
    main()
