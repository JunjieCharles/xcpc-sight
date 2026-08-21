"""Predict Nowcoder/HDU problem ratings from xcpc-sight series data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Iterable

import httpx
import pandas as pd
from sklearn.base import clone

from .build_problem_features import DEFAULT_OUTPUT
from .experiment_models import build_models, prepare_features
from .problem_features import (
    kernel_solve_curve,
    sliding_window_solve_curve,
    summarize_solve_times,
)
from .solve_features import calculate_solve_features


NOWCODER_IDS = tuple(range(133876, 133886))
HDU_IDS = tuple(range(1229, 1239))
CENTERS = tuple(range(800, 3501, 100))
HDU_MISSING_TITLE = "官方 guest 数据未提供题名"
NOWCODER_MISSING_TITLE = "官方公开页面未提供题名"


@dataclass(frozen=True)
class Participant:
    rating: float
    accepted_times: dict[str, float]
    team_size: int


@dataclass(frozen=True)
class ContestData:
    series: str
    contest_id: int
    contest_name: str
    start_seconds: float
    duration_seconds: float
    problems: tuple[tuple[str, str], ...]
    participants: tuple[Participant, ...]


def stable_competitor_id(source: str, key: str) -> str:
    identity = f"{source}\0{key}".encode()
    return f"c_{hashlib.sha256(identity).hexdigest()}"


def load_series(path: Path) -> tuple[dict, dict[str, int]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    ratings = {
        competitor["id"]: int(competitor["finalRating"])
        for competitor in document["competitors"]
    }
    return document, ratings


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
            competitor_id = stable_competitor_id(
                "nowcoder", f"standing:{row['uid']}"
            )
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
        contest_id
        for contest_id in HDU_IDS
        if not hdu_cache_path(cache_dir, contest_id).exists()
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
    payload = json.loads(
        hdu_cache_path(cache_dir, contest_id).read_text(encoding="utf-8")
    )
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
        participants.append(
            Participant(float(rating), accepted_times, team_size=3)
        )

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

        for problem_order, (problem_index, problem_name) in enumerate(
            contest.problems, start=1
        ):
            solved_flags = [problem_index in user_solves for user_solves in solves]
            solved_count = sum(solved_flags)
            time_records = [
                (participant.rating, user_solves[problem_index])
                for participant, user_solves in zip(
                    contest.participants, solves, strict=True
                )
                if participant.rating >= 1600 and problem_index in user_solves
            ]
            solved_team_sizes = [
                participant.team_size
                for participant, solved in zip(
                    contest.participants, solved_flags, strict=True
                )
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
                "teamSizeMedian": (
                    float(median(solved_team_sizes)) if solved_team_sizes else None
                ),
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
    cached = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )
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
                raise RuntimeError(
                    f"Nowcoder {contest_id}: problem-list returned {payload!r}"
                )
            for problem in payload["data"]["data"]:
                problem_id = str(problem["problemId"])
                title = str(problem["title"]).strip()
                cached[problem_id] = title or f"Nowcoder problem {problem_id}"
    still_missing = problem_ids - set(cached)
    if still_missing:
        raise RuntimeError(
            f"Nowcoder problem-list omitted {len(still_missing)} problem titles"
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cached, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cached


def collect_nowcoder_problem_ids(paths: Iterable[Path]) -> set[str]:
    problem_ids = set()
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            row = next(reader)
            problem_ids.update(
                value
                for column, value in row.items()
                if column.endswith("_problem_id")
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
            ("nowcoder-summer-2026", "牛客"),
            ("hdu-summer-2026", "HDU"),
        ]:
            table = result.loc[result["series"] == series, list(columns)].rename(
                columns=columns
            )
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
    parser.add_argument("--xcpc-root", type=Path, required=True)
    parser.add_argument("--training-features", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("outputs/analysis/xcpc_cache"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/analysis/xcpc_problem_ratings.csv"),
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=Path("outputs/analysis/xcpc_problem_ratings.md"),
    )
    parser.add_argument(
        "--output-xlsx",
        type=Path,
        default=Path("outputs/analysis/xcpc_problem_ratings.xlsx"),
    )
    args = parser.parse_args()

    nowcoder_document, nowcoder_ratings = load_series(
        args.xcpc_root / "static/data/series/nowcoder-summer-2026.json"
    )
    hdu_document, hdu_ratings = load_series(
        args.xcpc_root / "static/data/series/hdu-summer-2026.json"
    )
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
        load_hdu_contest(contest, hdu_ratings, hdu_cache)
        for contest in hdu_document["contests"]
    ]
    result = predict(
        build_feature_rows([*nowcoder_contests, *hdu_contests]),
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
