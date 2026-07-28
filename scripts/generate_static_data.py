from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import (
    HduClient,
    NowcoderClient,
    RankLandClient,
    load_2025_2026_season,
    nowcoder_leaderboard_to_contest,
)
from core.models import Contest
from rating import (
    calculate_series_ratings,
    project_series_rating_data,
    project_static_data_index,
)


@dataclass(frozen=True, slots=True)
class SeriesSpec:
    series_id: str
    title: str
    path: str
    load: Callable[[], tuple[Contest, ...]]


XCPC_SERIES_ID = "2025-2026"
XCPC_SERIES_TITLE = "2025–2026 ICPC + CCPC"
NOWCODER_SERIES_ID = "nowcoder-summer-2026"
NOWCODER_SERIES_TITLE = "2026牛客暑期多校训练营"
NOWCODER_CONTESTS = (
    (133876, "2026牛客暑期多校训练营（第一场）"),
    (133877, "2026牛客暑期多校训练营（第二场）"),
    (133878, "2026牛客暑期多校训练营（第三场）"),
)
HDU_SERIES_ID = "hdu-summer-2026"
HDU_SERIES_TITLE = '2026“钉耙编程”中国大学生算法设计暑期联赛'
HDU_CONTEST_IDS = (1229, 1230, 1231)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate static rating JSON data")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("static/data"),
        help="directory for generated JSON files (default: static/data)",
    )
    return parser.parse_args()


def write_json_atomic(output_path: Path, document: Any) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        serialized = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        temporary_path.write_text(f"{serialized}\n", encoding="utf-8", newline="\n")
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_xcpc_series() -> tuple[Contest, ...]:
    with RankLandClient() as client:
        return load_2025_2026_season(client).contests


def load_nowcoder_series() -> tuple[Contest, ...]:
    with NowcoderClient() as client:
        contests = tuple(
            nowcoder_leaderboard_to_contest(
                client.fetch_leaderboard(contest_id), title=title
            )
            for contest_id, title in NOWCODER_CONTESTS
        )
    return tuple(sorted(contests, key=lambda contest: contest.start_at))


def load_hdu_series() -> tuple[Contest, ...]:
    with HduClient() as client:
        contests = tuple(client.fetch_contest(contest_id) for contest_id in HDU_CONTEST_IDS)
    return tuple(sorted(contests, key=lambda contest: contest.start_at))


def series_specs() -> tuple[SeriesSpec, ...]:
    return (
        SeriesSpec(
            XCPC_SERIES_ID,
            XCPC_SERIES_TITLE,
            f"series/{XCPC_SERIES_ID}.json",
            load_xcpc_series,
        ),
        SeriesSpec(
            NOWCODER_SERIES_ID,
            NOWCODER_SERIES_TITLE,
            f"series/{NOWCODER_SERIES_ID}.json",
            load_nowcoder_series,
        ),
        SeriesSpec(
            HDU_SERIES_ID,
            HDU_SERIES_TITLE,
            f"series/{HDU_SERIES_ID}.json",
            load_hdu_series,
        ),
    )


def generate_static_data(output_dir: Path) -> None:
    publications: list[tuple[dict[str, object], str]] = []
    for spec in series_specs():
        contests = spec.load()
        result = calculate_series_ratings(contests)
        document = project_series_rating_data(
            result,
            series_id=spec.series_id,
            title=spec.title,
        )
        publications.append((document, spec.path))

    index = project_static_data_index(publications)
    for document, path in publications:
        write_json_atomic(output_dir / path, document)
    write_json_atomic(output_dir / "index.json", index)


def main() -> int:
    args = parse_args()
    generate_static_data(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
