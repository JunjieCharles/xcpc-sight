from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core import DataValidationError, DefaultNormalizer, load_school_aliases
from rating import normalized_lse_rating

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
SPECIAL_ACHIEVEMENTS = {
    "沈吉滪": [
        {"competition": "ioi", "year": 2024, "medal": "participant"},
    ],
}


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
    def __init__(
        self, records: list[PersonRecord], normalizer: DefaultNormalizer,
        *, sum_matches: bool = False,
    ) -> None:
        self.normalizer = normalizer
        self.sum_matches = sum_matches
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
        if self.sum_matches:
            # CPC Finder splits accumulated achievements across spelling variants.
            return PersonRecord(
                member_key, school_key,
                round(math.fsum(item.rating for item in matched), 2),
                tuple(sum(item.medals[i] for item in matched) for i in range(3)),
            )
        # Duplicate historical identities occasionally survive upstream cleanup. The highest
        # rating is the deterministic identity-resolution policy, before team aggregation.
        return max(matched, key=lambda item: (item.rating, item.medals, item.school, item.name))


class AchievementIndex:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.by_name: dict[str, list[dict[str, object]]] = {}
        for record in records:
            name = str(record["name"])
            achievement = {key: value for key, value in record.items() if key != "name"}
            self.by_name.setdefault(name, []).append(achievement)
        for achievements in self.by_name.values():
            achievements.sort(
                key=lambda item: (int(item["year"]), item["competition"] == "ioi")
            )

    def match(self, name: str) -> list[dict[str, object]]:
        return [dict(item) for item in self.by_name.get(name, ())]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manually requested ICPC preview snapshot"
    )
    parser.add_argument("--teams", type=Path, required=True)
    parser.add_argument("--xcpcrating-data", type=Path, required=True)
    parser.add_argument("--xcpc-elo-data", type=Path, required=True)
    parser.add_argument("--previous-series", type=Path, required=True)
    parser.add_argument("--history-srk-root", type=Path,
                        help="Local SRK collection for previous-season team histories")
    parser.add_argument("--current-series", type=Path)
    parser.add_argument("--cpcfinder-pages", type=Path, required=True)
    parser.add_argument(
        "--school-aliases", type=Path,
        default=Path(__file__).resolve().parents[1] / "config/school-aliases.json",
    )
    parser.add_argument("--noi-data", type=Path, default=Path("data-cache/noi/normalized"))
    parser.add_argument("--ioi-data", type=Path, default=Path("data-cache/ioi"))
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--preview-id", default=PREVIEW_ID)
    parser.add_argument("--preview-title", default=PREVIEW_TITLE)
    parser.add_argument("--team-source-url", default=TEAM_SOURCE_URL)
    parser.add_argument("--sort-at", default="2026-09-06T13:00:00+08:00")
    parser.add_argument("--cpcfinder-snapshot-date")
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
    return DefaultNormalizer(school_aliases=load_school_aliases(path))


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


def competition_ranks(scores: list[int | float]) -> list[int]:
    rank_by_score: dict[int | float, int] = {}
    for rank, score in enumerate(sorted(scores, reverse=True), start=1):
        rank_by_score.setdefault(score, rank)
    return [rank_by_score[score] for score in scores]


def load_achievements(noi_root: Path, ioi_root: Path) -> AchievementIndex:
    records: list[dict[str, object]] = []
    noi_index = load_json(noi_root / "index.json")
    for entry in noi_index["years"]:
        document = load_json(noi_root / entry["path"])
        awards = document["awards"]
        ranks = competition_ranks([award["score"] for award in awards])
        records.extend(
            {
                "name": award["name"],
                "competition": "noi",
                "year": document["year"],
                "medal": award["medal"],
                "rank": rank,
                "score": award["score"],
                "maxScore": 705,
            }
            for award, rank in zip(awards, ranks, strict=True)
        )
    ioi_index = load_json(ioi_root / "index.json")
    for entry in ioi_index["years"]:
        document = load_json(ioi_root / entry["path"])
        records.extend(
            {
                "name": result["name"],
                "competition": "ioi",
                "year": document["year"],
                "medal": result["medal"],
                "rank": result["rank"],
                "score": result["score"],
                "maxScore": document["max_score"],
            }
            for result in document["results"]
        )
    records.extend(
        {"name": name, **achievement}
        for name, achievements in SPECIAL_ACHIEVEMENTS.items()
        for achievement in achievements
    )
    return AchievementIndex(records)


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
    achievements = load_achievements(args.noi_data, args.ioi_data)
    indexes = {
        "xcpcrating": PersonIndex(xcpcrating, normalizer),
        "xcpcElo": PersonIndex(xcpc_elo, normalizer),
        "previousSeason": PersonIndex(previous, normalizer),
        "cpcfinder": PersonIndex(cpcfinder, normalizer, sum_matches=True),
    }
    metric_sources = list(METRIC_SOURCES)
    current_snapshots = {}
    if args.current_series:
        current_document = load_json(args.current_series)
        if current_document["id"] != SERIES_ID:
            raise ValueError(f"{args.current_series}: expected series {SERIES_ID}")
        current, current_at = load_previous_series(args.current_series)
        if datetime.fromisoformat(current_at) >= datetime.fromisoformat(args.sort_at):
            raise ValueError(f"{args.current_series}: current ratings must precede the preview")
        indexes["currentSeason"] = PersonIndex(current, normalizer)
        metric_sources.insert(3, ("currentSeason", "本赛季 Rating", f"./?series={SERIES_ID}"))
        current_snapshots["currentSeason"] = current_at
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
                    "achievements": achievements.match(name),
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
                    source_id: (max(values) if values else None)
                    if source_id == "cpcfinder" else normalized_lse_rating(values)
                    for source_id, values in team_ratings.items()
                },
                "medals": {
                    "gold": medal_totals[0],
                    "silver": medal_totals[1],
                    "bronze": medal_totals[2],
                },
            }
        )
    if getattr(args, "history_srk_root", None):
        from scripts.preview_history import build_history_index, team_history

        history_series = load_json(args.previous_series)
        year = int(SERIES_ID.split("-")[0])
        if history_series["id"] != f"{year - 1}-{year}":
            raise ValueError(f"{args.previous_series}: history must come from the previous season")
        history_index = build_history_index(history_series, args.history_srk_root, normalizer)
        for team in teams:
            team["previousSeasonHistory"] = team_history(team, history_index, normalizer)
    member_count = sum(len(team["members"]) for team in teams)
    return {
        "schemaVersion": 1,
        "ratingAggregation": "normalized-lse",
        "seriesId": SERIES_ID,
        "seriesTitle": SERIES_TITLE,
        "id": args.preview_id,
        "title": args.preview_title,
        "sortAt": args.sort_at,
        "snapshotDate": args.snapshot_date,
        "teamSource": {
            "title": "ICPC 报名系统队伍公示",
            "url": args.team_source_url,
            "note": "外部报名名单静态快照；不来自 Pintia 比赛榜单，不随比赛进程自动更新。",
        },
        "metricSources": [
            {"id": source_id, "title": title, "url": url}
            for source_id, title, url in metric_sources
        ],
        "sourceSnapshots": {
            "xcpcrating": xcpcrating_at,
            "xcpcElo": xcpc_elo_at,
            "previousSeason": previous_at,
            "cpcfinder": args.cpcfinder_snapshot_date or args.snapshot_date,
            **current_snapshots,
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
