"""Predict RankLand/Nowcoder/HDU problem ratings from xcpc-sight series data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

import httpx
import pandas as pd
from sklearn.base import clone

from core import normalize_srk_contest
from core.errors import DataValidationError
from core.normalization import DefaultNormalizer, is_coach_name

from .build_problem_features import DEFAULT_OUTPUT
from .experiment_models import build_models, prepare_features
from .paths import ANALYSIS_DIR, PROJECT_ROOT
from .problem_features import (
    kernel_solve_curve,
    sliding_window_solve_curve,
    summarize_solve_times,
)
from .solve_features import calculate_solve_features

NOWCODER_IDS = tuple(range(133876, 133886))
HDU_IDS = tuple(range(1229, 1239))
RANKLAND_SERIES_ID = "2025-2026"
CENTERS = tuple(range(800, 3501, 100))
HDU_MISSING_TITLE = "官方 guest 数据未提供题名"
NOWCODER_MISSING_TITLE = "官方公开页面未提供题名"
RANKLAND_MISSING_TITLE = "RankLand 公开榜单未提供题名"


@dataclass(frozen=True)
class Participant:
    rating: float
    accepted_times: dict[str, float]
    team_size: int


@dataclass(frozen=True)
class ContestData:
    series: str
    contest_id: str | int
    contest_name: str
    start_seconds: float
    duration_seconds: float
    problems: tuple[tuple[str, str], ...]
    participants: tuple[Participant, ...]


def stable_competitor_id(source: str, key: str) -> str:
    identity = f"{source}\0{key}".encode()
    return f"c_{hashlib.sha256(identity).hexdigest()}"


def stable_member_competitor_id(
    school: str,
    member: str,
    *,
    normalizer: DefaultNormalizer | None = None,
) -> str:
    """Return the participant-series ID for one normalized school/member identity."""
    competitor = (normalizer or DefaultNormalizer()).competitor(school, member)
    identity = f"{competitor.school}\0{competitor.member}".encode()
    return f"c_{hashlib.sha256(identity).hexdigest()}"


def max_member_rating(
    school: str,
    members: Iterable[str],
    ratings: dict[str, int],
    *,
    normalizer: DefaultNormalizer | None = None,
) -> int | None:
    """Return max(all member ratings), or None unless every member can be mapped."""
    normalizer = normalizer or DefaultNormalizer()
    member_ids = [
        stable_member_competitor_id(school, member, normalizer=normalizer)
        for member in members
        if member.strip() and not is_coach_name(member)
    ]
    if not member_ids or any(member_id not in ratings for member_id in member_ids):
        return None
    return max(ratings[member_id] for member_id in member_ids)


def load_series(path: Path) -> tuple[dict, dict[str, int]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    ratings = {
        competitor["id"]: int(competitor["finalRating"]) for competitor in document["competitors"]
    }
    return document, ratings


def _rankland_cache_path(cache_dir: Path, contest_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", contest_id):
        raise DataValidationError(f"unsafe RankLand contest ID {contest_id!r}")
    return cache_dir / f"rankland-{contest_id}.json"


def _rankland_envelope(response: httpx.Response, context: str) -> dict:
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise DataValidationError(f"{context}: response must be JSON") from error
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise DataValidationError(f"{context}: unsuccessful RankLand response")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise DataValidationError(f"{context}: data must be an object")
    return data


def fetch_rankland_caches(contests: Iterable[dict], cache_dir: Path) -> None:
    """Cache public SRK payloads with source provenance for offline prediction."""
    missing = [
        contest
        for contest in contests
        if not _rankland_cache_path(cache_dir, str(contest["id"])).exists()
    ]
    if not missing:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    api_root = "https://rl.algoux.cn/api/v2"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for contest in missing:
            contest_id = str(contest["id"])
            print(f"Fetching RankLand {contest_id}...", flush=True)
            detail = _rankland_envelope(
                client.get(f"{api_root}/public/contests/{contest_id}"),
                f"RankLand contest {contest_id}",
            )
            file_id = detail.get("srkFileID")
            if not isinstance(file_id, str) or not file_id:
                raise DataValidationError(f"RankLand contest {contest_id}: missing srkFileID")
            metadata = _rankland_envelope(
                client.get(f"{api_root}/public/files/{file_id}"),
                f"RankLand file {file_id}",
            )
            file_url = metadata.get("url")
            if not isinstance(file_url, str) or not file_url.startswith("https://"):
                raise DataValidationError(f"RankLand file {file_id}: invalid public URL")
            source = client.get(file_url)
            source.raise_for_status()
            expected_hash = metadata.get("hashValue")
            actual_hash = hashlib.sha256(source.content).hexdigest()
            if isinstance(expected_hash, str) and expected_hash and expected_hash != actual_hash:
                raise DataValidationError(
                    f"RankLand contest {contest_id}: SRK sha256 does not match metadata"
                )
            try:
                srk = source.json()
            except ValueError as error:
                raise DataValidationError(
                    f"RankLand contest {contest_id}: SRK file must be JSON"
                ) from error
            if not isinstance(srk, dict):
                raise DataValidationError(
                    f"RankLand contest {contest_id}: SRK root must be an object"
                )
            cached = {
                "contestId": contest_id,
                "fileId": file_id,
                "fileUrl": file_url,
                "sha256": actual_hash,
                "srk": srk,
            }
            _rankland_cache_path(cache_dir, contest_id).write_text(
                json.dumps(cached, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )


def _rankland_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for key in ("zh-CN", "fallback", "en"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _rankland_seconds(value: object, context: str) -> float:
    if not isinstance(value, list) or not value:
        raise DataValidationError(f"{context}: expected [amount, unit]")
    amount = value[0]
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        raise DataValidationError(f"{context}: duration amount must be non-negative")
    unit = str(value[1] if len(value) > 1 else "min").casefold()
    multiplier = {
        "ms": 0.001,
        "millisecond": 0.001,
        "milliseconds": 0.001,
        "s": 1.0,
        "sec": 1.0,
        "second": 1.0,
        "seconds": 1.0,
        "min": 60.0,
        "minute": 60.0,
        "minutes": 60.0,
        "h": 3600.0,
        "hour": 3600.0,
        "hours": 3600.0,
    }.get(unit)
    if multiplier is None:
        raise DataValidationError(f"{context}: unsupported duration unit {unit!r}")
    return float(amount) * multiplier


def _rankland_accepted_seconds(status: object, context: str) -> float | None:
    if not isinstance(status, dict) or status.get("result") not in {"AC", "FB"}:
        return None
    if status.get("time") is not None:
        return max(_rankland_seconds(status["time"], f"{context}.time"), 1.0)
    solutions = status.get("solutions")
    if isinstance(solutions, list):
        for solution in reversed(solutions):
            if (
                isinstance(solution, dict)
                and solution.get("result") in {"AC", "FB"}
                and solution.get("time") is not None
            ):
                return max(
                    _rankland_seconds(solution["time"], f"{context}.solutions.time"),
                    1.0,
                )
    raise DataValidationError(f"{context}: accepted status has no accepted time")


def _rankland_competitor_names(raw_row: dict, context: str) -> tuple[str, ...]:
    user = raw_row.get("user")
    if not isinstance(user, dict):
        raise DataValidationError(f"{context}.user must be an object")
    raw_members = user.get("teamMembers")
    if not isinstance(raw_members, list):
        raise DataValidationError(f"{context}.user.teamMembers must be an array")

    members: list[str] = []
    for member_index, raw_member in enumerate(raw_members):
        if not isinstance(raw_member, dict):
            raise DataValidationError(
                f"{context}.user.teamMembers[{member_index}] must be an object"
            )
        name = _rankland_text(raw_member.get("name"))
        role = _rankland_text(raw_member.get("role")).casefold()
        if not name or role == "coach" or is_coach_name(name):
            continue
        members.append(name)

    if len(raw_members) == 1 and len(members) == 1 and len(members[0].split()) >= 3:
        return tuple(members[0].split())
    return tuple(members)


def load_rankland_contest(
    contest: dict,
    ratings: dict[str, int],
    cache_dir: Path,
) -> ContestData:
    """Adapt one cached RankLand SRK contest using max member final rating per team."""
    contest_id = str(contest["id"])
    cache_path = _rankland_cache_path(cache_dir, contest_id)
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataValidationError(f"unable to read RankLand cache {cache_path}") from error
    if not isinstance(cached, dict) or cached.get("contestId") != contest_id:
        raise DataValidationError(f"RankLand cache {cache_path}: contest ID mismatch")
    srk = cached.get("srk")
    if not isinstance(srk, dict):
        raise DataValidationError(f"RankLand cache {cache_path}: srk must be an object")
    normalized = normalize_srk_contest(
        srk,
        contest_uk=contest_id,
        series=RANKLAND_SERIES_ID,
    )
    raw_problems = srk.get("problems")
    raw_rows = srk.get("rows")
    if not isinstance(raw_problems, list) or not raw_problems:
        raise DataValidationError(f"RankLand contest {contest_id}: problems must be non-empty")
    if not isinstance(raw_rows, list) or len(raw_rows) != len(normalized.teams):
        raise DataValidationError(f"RankLand contest {contest_id}: rows do not match teams")

    problems: list[tuple[str, str]] = []
    seen_problem_ids: set[str] = set()
    for problem_index, raw_problem in enumerate(raw_problems):
        if not isinstance(raw_problem, dict):
            raise DataValidationError(
                f"RankLand contest {contest_id}.problems[{problem_index}] must be an object"
            )
        alias = _rankland_text(raw_problem.get("alias"))
        if not alias or alias in seen_problem_ids:
            raise DataValidationError(
                f"RankLand contest {contest_id}.problems[{problem_index}]: invalid alias"
            )
        seen_problem_ids.add(alias)
        title = _rankland_text(raw_problem.get("title")) or _rankland_text(raw_problem.get("name"))
        problems.append((alias, title or RANKLAND_MISSING_TITLE))

    participants: list[Participant] = []
    excluded_teams: list[str] = []
    normalizer = DefaultNormalizer()
    for row_index, (raw_row, team) in enumerate(zip(raw_rows, normalized.teams, strict=True)):
        if not team.official or not team.has_activity:
            continue
        if not isinstance(raw_row, dict):
            raise DataValidationError(
                f"RankLand contest {contest_id}.rows[{row_index}] must be an object"
            )
        row_context = f"RankLand contest {contest_id}.rows[{row_index}]"
        members = _rankland_competitor_names(raw_row, row_context)
        rating = max_member_rating(
            team.school_name,
            members,
            ratings,
            normalizer=normalizer,
        )
        if rating is None:
            excluded_teams.append(team.team_id)
            continue
        statuses = raw_row.get("statuses")
        if statuses is None:
            statuses = []
        if not isinstance(statuses, list) or len(statuses) > len(problems):
            raise DataValidationError(
                f"RankLand contest {contest_id}.rows[{row_index}].statuses is invalid"
            )
        accepted_times = {}
        for status_index, status in enumerate(statuses):
            accepted = _rankland_accepted_seconds(
                status,
                f"RankLand contest {contest_id}.rows[{row_index}].statuses[{status_index}]",
            )
            if accepted is not None:
                accepted_times[problems[status_index][0]] = accepted
        participants.append(
            Participant(
                rating=float(rating),
                accepted_times=accepted_times,
                team_size=max(len(members), 1),
            )
        )

    if excluded_teams:
        print(
            f"Excluding RankLand {contest_id}: {len(excluded_teams)} active official "
            "teams do not map every member to a published final rating",
            flush=True,
        )
    if not participants:
        raise DataValidationError(f"RankLand contest {contest_id}: no rated participants")
    raw_contest = srk.get("contest")
    if not isinstance(raw_contest, dict):
        raise DataValidationError(f"RankLand contest {contest_id}: contest must be an object")
    start = datetime.fromisoformat(str(contest["startAt"]))
    return ContestData(
        series=RANKLAND_SERIES_ID,
        contest_id=contest_id,
        contest_name=str(contest["title"]),
        start_seconds=start.timestamp(),
        duration_seconds=_rankland_seconds(
            raw_contest.get("duration"),
            f"RankLand contest {contest_id}.duration",
        ),
        problems=tuple(problems),
        participants=tuple(participants),
    )


def parse_bool(value: str) -> bool:
    return value.strip().casefold() == "true"


def find_nowcoder_csv(
    contest_id: int,
    *,
    xcpc_root: Path,
    local_cache: Path,
) -> Path:
    name = f"nowcoder-{contest_id}-leaderboard.csv"
    candidates = [xcpc_root / "data-cache" / "nowcoder" / name, local_cache / name]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"missing Nowcoder leaderboard cache for {contest_id}")


def load_nowcoder_contest(
    contest: dict,
    ratings: dict[str, int],
    *,
    xcpc_root: Path,
    local_cache: Path,
    titles: dict[str, str],
) -> ContestData:
    contest_id = int(str(contest["id"]).split(":", 1)[1])
    csv_path = find_nowcoder_csv(
        contest_id,
        xcpc_root=xcpc_root,
        local_cache=local_cache,
    )
    start = datetime.fromisoformat(contest["startAt"])
    start_ms = start.timestamp() * 1000
    participants = []
    missing_ratings = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        problem_labels = tuple(
            column.removesuffix("_problem_id")
            for column in reader.fieldnames or ()
            if column.endswith("_problem_id")
        )
        problem_ids: dict[str, str] = {}
        for row in reader:
            for label in problem_labels:
                problem_ids.setdefault(label, row[f"{label}_problem_id"])
            has_activity = int(row["accepted_count"]) > 0 or any(
                parse_bool(row[f"{label}_submit"]) for label in problem_labels
            )
            if not has_activity:
                continue
            competitor_id = stable_competitor_id("nowcoder", f"standing:{row['uid']}")
            rating = ratings.get(competitor_id)
            if rating is None:
                missing_ratings.append(row["uid"])
                continue
            accepted_times = {}
            for label in problem_labels:
                if not parse_bool(row[f"{label}_accepted"]):
                    continue
                accepted_ms = int(row[f"{label}_accepted_time_ms"])
                accepted_times[label] = max((accepted_ms - start_ms) / 1000, 1.0)
            members = json.loads(row["team_member_uids"])
            participants.append(
                Participant(
                    rating=float(rating),
                    accepted_times=accepted_times,
                    team_size=max(len(members), 1),
                )
            )

    if missing_ratings:
        print(
            f"Excluding Nowcoder {contest_id}: {len(missing_ratings)} active "
            "cached standings have no published final rating",
            flush=True,
        )

    problems = tuple(
        (
            label,
            titles.get(problem_ids[label], f"Nowcoder problem {problem_ids[label]}"),
        )
        for label in problem_labels
    )
    return ContestData(
        series="nowcoder-summer-2026",
        contest_id=contest_id,
        contest_name=contest["title"],
        start_seconds=start.timestamp(),
        duration_seconds=5 * 60 * 60,
        problems=problems,
        participants=tuple(participants),
    )


def parse_hdu_accepted_time(cell: str) -> float | None:
    match = re.match(r"^(\d+):(\d{2}):(\d{2})(?:\s|$)", cell.strip())
    if match is None:
        return None
    hours, minutes, seconds = map(int, match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def hdu_cache_path(cache_dir: Path, contest_id: int) -> Path:
    return cache_dir / f"hdu-{contest_id}-leaderboard.json"


def fetch_hdu_caches(cache_dir: Path, xcpc_root: Path) -> None:
    missing = [
        contest_id for contest_id in HDU_IDS if not hdu_cache_path(cache_dir, contest_id).exists()
    ]
    if not missing:
        return
    sys.path.insert(0, str(xcpc_root / "src"))
    from core import HduClient  # noqa: PLC0415

    cache_dir.mkdir(parents=True, exist_ok=True)
    with HduClient() as client:
        for contest_id in missing:
            print(f"Fetching HDU {contest_id}...", flush=True)
            leaderboard = client.fetch_leaderboard(contest_id)
            payload = {
                "contestId": contest_id,
                "title": leaderboard.metadata.title,
                "startAt": leaderboard.metadata.start.isoformat(),
                "endAt": leaderboard.metadata.end.isoformat(),
                "problems": list(leaderboard.problem_headers),
                "standings": [
                    {
                        "teamToken": standing.team_token,
                        "problemCells": list(standing.problem_cells),
                    }
                    for standing in leaderboard.standings
                ],
            }
            hdu_cache_path(cache_dir, contest_id).write_text(
                json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def load_hdu_contest(contest: dict, ratings: dict[str, int], cache_dir: Path):
    contest_id = int(str(contest["id"]).split(":", 1)[1])
    payload = json.loads(hdu_cache_path(cache_dir, contest_id).read_text(encoding="utf-8"))
    participants = []
    missing_ratings = []
    for standing in payload["standings"]:
        cells = standing["problemCells"]
        if not any(cell.strip() for cell in cells):
            continue
        competitor_id = stable_competitor_id("hdu", standing["teamToken"])
        rating = ratings.get(competitor_id)
        if rating is None:
            missing_ratings.append(standing["teamToken"])
            continue
        accepted_times = {
            problem_id: accepted_time
            for problem_id, cell in zip(payload["problems"], cells, strict=True)
            if (accepted_time := parse_hdu_accepted_time(cell)) is not None
        }
        participants.append(Participant(float(rating), accepted_times, team_size=3))

    if missing_ratings:
        print(
            f"Excluding HDU {contest_id}: {len(missing_ratings)} active standings "
            "have no published final rating",
            flush=True,
        )

    start = datetime.fromisoformat(payload["startAt"])
    end = datetime.fromisoformat(payload["endAt"])
    problems = tuple((problem_id, HDU_MISSING_TITLE) for problem_id in payload["problems"])
    return ContestData(
        series="hdu-summer-2026",
        contest_id=contest_id,
        contest_name=contest["title"],
        start_seconds=start.timestamp(),
        duration_seconds=(end - start).total_seconds(),
        problems=problems,
        participants=tuple(participants),
    )


def build_feature_rows(contests: Iterable[ContestData]) -> list[dict]:
    rows = []
    for contest in contests:
        ratings = [participant.rating for participant in contest.participants]
        solves = []
        for participant in contest.participants:
            submissions = [
                {
                    "verdict": "OK",
                    "problem": {"index": problem_index},
                    "relativeTimeSeconds": accepted_time,
                }
                for problem_index, accepted_time in participant.accepted_times.items()
            ]
            solves.append(calculate_solve_features(submissions, max_previous=3))

        for problem_order, (problem_index, problem_name) in enumerate(contest.problems, start=1):
            solved_flags = [problem_index in user_solves for user_solves in solves]
            solved_count = sum(solved_flags)
            time_records = [
                (participant.rating, user_solves[problem_index])
                for participant, user_solves in zip(contest.participants, solves, strict=True)
                if participant.rating >= 1600 and problem_index in user_solves
            ]
            solved_team_sizes = [
                participant.team_size
                for participant, solved in zip(contest.participants, solved_flags, strict=True)
                if solved
            ]
            row = {
                "series": contest.series,
                "nativeContestId": contest.contest_id,
                "contestId": f"{contest.series}:{contest.contest_id}",
                "contestName": contest.contest_name,
                "contestStartTimeSeconds": contest.start_seconds,
                "contestDurationSeconds": contest.duration_seconds,
                "problemIndex": problem_index,
                "problemName": problem_name,
                "problemOrder": problem_order,
                "ratedProblemCount": len(contest.problems),
                "participantCount": len(contest.participants),
                "solvedCount": solved_count,
                "solveRate": (solved_count + 0.5) / (len(contest.participants) + 1),
                "teamSizeMedian": (float(median(solved_team_sizes)) if solved_team_sizes else None),
            }
            row.update(sliding_window_solve_curve(ratings, solved_flags, CENTERS))
            row.update(
                kernel_solve_curve(
                    ratings,
                    solved_flags,
                    CENTERS,
                    bandwidth=100,
                    kernel="gaussian",
                )
            )
            row.update(summarize_solve_times(time_records))
            rows.append(row)
    return rows


def fetch_nowcoder_problem_titles(
    problem_ids: set[str],
    contest_ids: Iterable[int],
    cache_path: Path,
):
    cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    unavailable = {
        problem_id
        for problem_id, title in cached.items()
        if title == NOWCODER_MISSING_TITLE
        or "没有查看题目的权限" in title
        or "付费比赛题目" in title
    }
    if problem_ids <= set(cached) and not unavailable:
        return cached
    url = "https://ac.nowcoder.com/acm/contest/problem-list"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        for contest_id in contest_ids:
            response = client.get(
                url,
                params={"id": contest_id},
                headers={"Referer": f"https://ac.nowcoder.com/acm/contest/{contest_id}"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"Nowcoder {contest_id}: problem-list returned {payload!r}")
            for problem in payload["data"]["data"]:
                problem_id = str(problem["problemId"])
                title = str(problem["title"]).strip()
                cached[problem_id] = title or f"Nowcoder problem {problem_id}"
    still_missing = problem_ids - set(cached)
    if still_missing:
        raise RuntimeError(f"Nowcoder problem-list omitted {len(still_missing)} problem titles")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cached


def collect_nowcoder_problem_ids(paths: Iterable[Path]) -> set[str]:
    problem_ids = set()
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            row = next(reader)
            problem_ids.update(
                value for column, value in row.items() if column.endswith("_problem_id")
            )
    return problem_ids


def predict(rows: list[dict], training_path: Path) -> pd.DataFrame:
    training = pd.read_csv(training_path)
    prepared_training, training_families = prepare_features(training)
    test = pd.DataFrame(rows)
    prepared_test, test_families = prepare_features(test)
    feature_name = "gaussian + prev1-3"
    if training_families[feature_name] != test_families[feature_name]:
        raise RuntimeError("training and XCPC feature schemas do not match")
    columns = training_families[feature_name]
    model = clone(build_models()["Shallow GBR"])
    model.fit(prepared_training[columns], prepared_training["problemRating"])
    result = test[
        [
            "series",
            "nativeContestId",
            "contestName",
            "problemIndex",
            "problemName",
            "solvedCount",
            "participantCount",
            "timeSampleCount",
        ]
    ].copy()
    raw = model.predict(prepared_test[columns])
    result["predictedRating"] = [int(math.floor(value + 0.5)) for value in raw]
    return result


def write_markdown_tables(result: pd.DataFrame, output_path: Path) -> None:
    lines = []
    for series, heading in [
        (RANKLAND_SERIES_ID, "2025–2026 ICPC + CCPC"),
        ("nowcoder-summer-2026", "牛客 2026 暑期多校"),
        ("hdu-summer-2026", "HDU 2026 暑期多校"),
    ]:
        lines.extend(
            [
                f"## {heading}",
                "",
                "| 比赛场次名 | 题目号 | 题目名 | 通过队伍数 | 总有效队伍数 | 预测rating |",
                "|---|---:|---|---:|---:|---:|",
            ]
        )
        subset = result[result["series"] == series]
        for row in subset.itertuples(index=False):
            name = str(row.problemName).replace("|", "\\|")
            lines.append(
                f"| {row.contestName} | {row.problemIndex} | {name} | "
                f"{row.solvedCount} | {row.participantCount} | {row.predictedRating} |"
            )
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_excel_tables(result: pd.DataFrame, output_path: Path) -> None:
    columns = {
        "contestName": "比赛场次名",
        "problemIndex": "题目号",
        "problemName": "题目名",
        "solvedCount": "通过队伍数",
        "participantCount": "总有效队伍数",
        "predictedRating": "预测rating",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for series, sheet_name in [
            (RANKLAND_SERIES_ID, "ICPC+CCPC"),
            ("nowcoder-summer-2026", "牛客"),
            ("hdu-summer-2026", "HDU"),
        ]:
            table = result.loc[result["series"] == series, list(columns)].rename(columns=columns)
            table.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                width = min(
                    max(len(str(cell.value or "")) for cell in column_cells) + 2,
                    48,
                )
                worksheet.column_dimensions[column_cells[0].column_letter].width = width


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xcpc-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--training-features", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ANALYSIS_DIR / "xcpc_cache",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ANALYSIS_DIR / "xcpc_problem_ratings.csv",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=ANALYSIS_DIR / "xcpc_problem_ratings.md",
    )
    parser.add_argument(
        "--output-xlsx",
        type=Path,
        default=ANALYSIS_DIR / "xcpc_problem_ratings.xlsx",
    )
    args = parser.parse_args()

    nowcoder_document, nowcoder_ratings = load_series(
        args.xcpc_root / "static/data/series/nowcoder-summer-2026.json"
    )
    hdu_document, hdu_ratings = load_series(
        args.xcpc_root / "static/data/series/hdu-summer-2026.json"
    )
    rankland_document, rankland_ratings = load_series(
        args.xcpc_root / "static/data/series/2025-2026.json"
    )
    rankland_cache = args.cache_dir / "rankland"
    fetch_rankland_caches(rankland_document["contests"], rankland_cache)
    rankland_contests = [
        load_rankland_contest(contest, rankland_ratings, rankland_cache)
        for contest in rankland_document["contests"]
    ]
    nowcoder_cache = args.cache_dir / "nowcoder"
    nowcoder_paths = [
        find_nowcoder_csv(
            contest_id,
            xcpc_root=args.xcpc_root,
            local_cache=nowcoder_cache,
        )
        for contest_id in NOWCODER_IDS
    ]
    titles = fetch_nowcoder_problem_titles(
        collect_nowcoder_problem_ids(nowcoder_paths),
        NOWCODER_IDS,
        args.cache_dir / "nowcoder_problem_titles.json",
    )
    nowcoder_contests = [
        load_nowcoder_contest(
            contest,
            nowcoder_ratings,
            xcpc_root=args.xcpc_root,
            local_cache=nowcoder_cache,
            titles=titles,
        )
        for contest in nowcoder_document["contests"]
    ]

    hdu_cache = args.cache_dir / "hdu"
    fetch_hdu_caches(hdu_cache, args.xcpc_root)
    hdu_contests = [
        load_hdu_contest(contest, hdu_ratings, hdu_cache) for contest in hdu_document["contests"]
    ]
    result = predict(
        build_feature_rows([*rankland_contests, *nowcoder_contests, *hdu_contests]),
        args.training_features,
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
    write_markdown_tables(result, args.output_markdown)
    write_excel_tables(result, args.output_xlsx)
    print(
        f"Wrote {len(result)} rows to {args.output_csv}, "
        f"{args.output_markdown}, and {args.output_xlsx}"
    )


if __name__ == "__main__":
    main()
