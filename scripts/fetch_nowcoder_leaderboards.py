from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from core import NowcoderClient, nowcoder_csv_fieldnames, nowcoder_csv_rows

DEFAULT_CONTEST_IDS = (
    133876,
    133877,
    133878,
    133879,
    133880,
    133881,
    133882,
    133883,
    133884,
    133885,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch complete Nowcoder contest leaderboards")
    parser.add_argument(
        "contest_ids",
        nargs="*",
        type=int,
        default=DEFAULT_CONTEST_IDS,
        help="Nowcoder contest IDs (defaults to 133876 through 133885)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data-cache/nowcoder"),
        help="directory for generated CSV files (default: data-cache/nowcoder)",
    )
    return parser.parse_args()


def write_leaderboard_csv(output_path: Path, leaderboard: object) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=nowcoder_csv_fieldnames(leaderboard))
            writer.writeheader()
            writer.writerows(nowcoder_csv_rows(leaderboard))
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    with NowcoderClient() as client:
        for contest_id in args.contest_ids:
            leaderboard = client.fetch_leaderboard(contest_id)
            output_path = args.output_dir / f"nowcoder-{contest_id}-leaderboard.csv"
            write_leaderboard_csv(output_path, leaderboard)
            print(
                f"contest {contest_id}: {leaderboard.rank_count} rows, "
                f"{len(leaderboard.problems)} problems -> {output_path}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
