from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from core import RankLandClient, load_2025_2026_season
from rating import (
    calculate_series_ratings,
    project_series_rating_data,
    project_static_data_index,
)

SERIES_ID = "2025-2026"
SERIES_TITLE = "2025–2026 ICPC + CCPC"
SERIES_PATH = f"series/{SERIES_ID}.json"


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


def generate_static_data(output_dir: Path) -> None:
    with RankLandClient() as client:
        season = load_2025_2026_season(client)
    result = calculate_series_ratings(season.contests)
    series = project_series_rating_data(
        result,
        series_id=SERIES_ID,
        title=SERIES_TITLE,
    )
    index = project_static_data_index(
        series_id=SERIES_ID,
        title=SERIES_TITLE,
        path=SERIES_PATH,
    )

    write_json_atomic(output_dir / SERIES_PATH, series)
    write_json_atomic(output_dir / "index.json", index)


def main() -> int:
    args = parse_args()
    generate_static_data(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
