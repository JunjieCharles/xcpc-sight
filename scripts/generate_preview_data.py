from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import DataValidationError, DefaultNormalizer

SERIES_ID = "2026-2027"
SERIES_TITLE = "2026–2027 ICPC + CCPC"
PREVIEW_ID = "icpc-2026-preliminary-1"
PREVIEW_TITLE = "2026 ICPC Asia EC网络预选赛 - 第一场"
TEAM_SOURCE_URL = (
    "https://uep.pintia.cn/icpc-reg/examGroups/2086678069855703040/publicTeams"
)
METRIC_SOURCES = (
    ("xcpcrating", "XCPC Rating", "https://github.com/Hei-MaoM/xcpcrating"),
    ("xcpcElo", "XCPC Elo", "https://github.com/Zzzzzzyt/xcpc-elo"),
    ("previousSeason", "上赛季 Rating", "./?series=2025-2026"),
    ("cpcfinder", "CPC Finder", "https://cpcfinder.com/"),
)


@dataclass(frozen=True, slots=True)
class PersonRecord:
    name: str
    school: str
    rating: int | float
    medals: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True, slots=True)
class RegisteredTeam:
    source_index: int
    name: str
    school: str
    members: tuple[str, ...]


class PersonIndex:
    def __init__(self, records: list[PersonRecord], normalizer: DefaultNormalizer) -> None:
        self.normalizer = normalizer
        self.by_name: dict[str, list[PersonRecord]] = {}
        for record in records:
            try:
                member_key = normalizer.member(record.name)
            except DataValidationError:
                continue
            self.by_name.setdefault(member_key, []).append(record)

    def match(self, name: str, school: str) -> PersonRecord | None:
        try:
            member_key = self.normalizer.member(name)
        except DataValidationError:
            return None
        candidates = self.by_name.get(member_key, ())
        school_key = self.normalizer.school(school)
        matched = [
            candidate
            for candidate in candidates
            if self.normalizer.school(candidate.school) == school_key
        ]
        if not matched:
            return None
        # Duplicate historical identities occasionally survive upstream cleanup. The highest
        # rating is deterministic and agrees with the team-level maximum display policy.
        return max(matched, key=lambda item: (item.rating, item.medals, item.school, item.name))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the manually requested ICPC 网络赛 1 preview snapshot"
    )
    parser.add_argument("--teams", type=Path, required=True)
    parser.add_argument("--xcpcrating-data", type=Path, required=True)
    parser.add_argument("--xcpc-elo-data", type=Path, required=True)
    parser.add_argument("--previous-series", type=Path, required=True)
    parser.add_argument("--cpcfinder-pages", type=Path, required=True)
    parser.add_argument("--school-aliases", type=Path, required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("static/data/previews/2026-2027.json"),
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        serialized = json.dumps(
            document, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        temporary.write_text(f"{serialized}\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_normalizer(path: Path) -> DefaultNormalizer:
    document = load_json(path)
    aliases = {
        alias: canonical
        for canonical, values in document.items()
        for alias in values
    }
    return DefaultNormalizer(school_aliases=aliases)


def load_xcpcrating(root: Path) -> tuple[list[PersonRecord], str]:
    records: list[PersonRecord] = []
    for path in sorted((root / "leaderboards" / "official" / "pages").glob("*.json")):
        for row in load_json(path):
            if len(row) >= 4 and isinstance(row[3], int | float):
                records.append(PersonRecord(str(row[1]), str(row[2]), round(row[3], 2)))
    generated_at = str(load_json(root / "meta.json")["generatedAt"])
    return records, generated_at


def load_xcpc_elo(path: Path) -> tuple[list[PersonRecord], str]:
    text = path.read_text(encoding="utf-8").strip()
    prefix = "window.__ELO_DATA__ = "
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"{path}: expected window.__ELO_DATA__ assignment")
    document = json.loads(text[len(prefix) : -1])
    initial = int(document["config"]["initialRating"])
    records = []
    for player in document["players"]:
        history = player.get("history") or []
        rating = int(history[-1][3]) if history else initial
        records.append(PersonRecord(player["name"], player["organization"], rating))
    return records, str(document["generatedAt"])


def load_previous_series(path: Path) -> tuple[list[PersonRecord], str]:
    document = load_json(path)
    records = [
        PersonRecord(item["member"], item["school"], int(item["finalRating"]))
        for item in document["competitors"]
    ]
    latest = max(contest["startAt"] for contest in document["contests"])
    return records, latest


def load_cpcfinder(root: Path) -> list[PersonRecord]:
    records = []
    for path in sorted(root.glob("*.json"), key=lambda item: int(item.stem)):
        for item in load_json(path)["data"]:
            records.append(
                PersonRecord(
                    item["name"],
                    item["schoolName"],
                    round(float(item.get("rating") or 0), 2),
                    (
                        int(item.get("goldCount") or 0),
                        int(item.get("silverCount") or 0),
                        int(item.get("bronzeCount") or 0),
                    ),
                )
            )
    return records


def stable_team_id(school: str, name: str, members: list[str]) -> str:
    identity = "\0".join((school, name, *members)).encode()
    return f"t_{hashlib.sha256(identity).hexdigest()[:20]}"


def parse_registered_team(row: object, source_index: int) -> RegisteredTeam:
    if not isinstance(row, list) or len(row) < 4:
        raise ValueError(f"team row {source_index}: expected at least four columns")
    team_name, _, school, member_text = (str(value).strip() for value in row[:4])
    members = tuple(
        part.strip() for part in re.split(r"\s*/\s*", member_text) if part.strip()
    )
    if not team_name or not school or not members:
        raise ValueError(f"team row {source_index}: missing team, school, or members")
    # The public registration table puts coaches in later columns. Deliberately consume
    # only the first four columns so coaches can never enter rating or medal aggregation.
    return RegisteredTeam(source_index, team_name, school, members)


def build_document(args: argparse.Namespace) -> dict[str, object]:
    normalizer = load_normalizer(args.school_aliases)
    xcpcrating, xcpcrating_at = load_xcpcrating(args.xcpcrating_data)
    xcpc_elo, xcpc_elo_at = load_xcpc_elo(args.xcpc_elo_data)
    previous, previous_at = load_previous_series(args.previous_series)
    cpcfinder = load_cpcfinder(args.cpcfinder_pages)
    indexes = {
        "xcpcrating": PersonIndex(xcpcrating, normalizer),
        "xcpcElo": PersonIndex(xcpc_elo, normalizer),
        "previousSeason": PersonIndex(previous, normalizer),
        "cpcfinder": PersonIndex(cpcfinder, normalizer),
    }
    match_counts = dict.fromkeys(indexes, 0)
    teams = []
    raw_teams = load_json(args.teams)
    for source_index, row in enumerate(raw_teams):
        registered = parse_registered_team(row, source_index)
        team_name = registered.name
        school = registered.school
        members = list(registered.members)
        member_documents = []
        team_ratings: dict[str, list[int | float]] = {key: [] for key in indexes}
        medal_totals = [0, 0, 0]
        for name in members:
            ratings: dict[str, int | float | None] = {}
            cpc_record: PersonRecord | None = None
            for source_id, index in indexes.items():
                record = index.match(name, school)
                ratings[source_id] = record.rating if record else None
                if record:
                    match_counts[source_id] += 1
                    team_ratings[source_id].append(record.rating)
                if source_id == "cpcfinder":
                    cpc_record = record
            medals = cpc_record.medals if cpc_record else (0, 0, 0)
            medal_totals = [left + right for left, right in zip(medal_totals, medals, strict=True)]
            member_documents.append(
                {
                    "name": name,
                    "ratings": ratings,
                    "medals": {
                        "gold": medals[0],
                        "silver": medals[1],
                        "bronze": medals[2],
                    },
                }
            )
        teams.append(
            {
                "id": stable_team_id(school, team_name, members),
                "sourceIndex": source_index,
                "school": school,
                "name": team_name,
                "members": member_documents,
                "ratings": {
                    source_id: max(values) if values else None
                    for source_id, values in team_ratings.items()
                },
                "medals": {
                    "gold": medal_totals[0],
                    "silver": medal_totals[1],
                    "bronze": medal_totals[2],
                },
            }
        )
    member_count = sum(len(team["members"]) for team in teams)
    return {
        "schemaVersion": 1,
        "seriesId": SERIES_ID,
        "seriesTitle": SERIES_TITLE,
        "id": PREVIEW_ID,
        "title": PREVIEW_TITLE,
        "sortAt": "2026-09-06T13:00:00+08:00",
        "snapshotDate": args.snapshot_date,
        "teamSource": {
            "title": "ICPC 报名系统队伍公示",
            "url": TEAM_SOURCE_URL,
            "note": "外部报名名单静态快照；不来自 Pintia 比赛榜单，不随比赛进程自动更新。",
        },
        "metricSources": [
            {"id": source_id, "title": title, "url": url}
            for source_id, title, url in METRIC_SOURCES
        ],
        "sourceSnapshots": {
            "xcpcrating": xcpcrating_at,
            "xcpcElo": xcpc_elo_at,
            "previousSeason": previous_at,
            "cpcfinder": args.snapshot_date,
        },
        "matchingPolicy": (
            "先按规范化人名查找，再要求规范化或别名学校完全匹配；"
            "不按人名唯一性猜测学校。"
        ),
        "matchingSummary": {
            "members": member_count,
            **{source_id: count for source_id, count in match_counts.items()},
        },
        "teams": teams,
    }


def main() -> int:
    args = parse_args()
    write_json_atomic(args.output, build_document(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
