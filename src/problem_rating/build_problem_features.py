"""Build cached problem-level features for model experiments."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .fetch_data import CodeforcesFetcher
from .paths import PROBLEM_FEATURE_FILE, PROCESSED_DATA_DIR, ensure_directory
from .problem_features import build_contest_problem_features


DEFAULT_OUTPUT = PROBLEM_FEATURE_FILE


def parse_centers(specification: str) -> list[int]:
    """Parse START:STOP:STEP, with an inclusive STOP."""

    try:
        start, stop, step = map(int, specification.split(":"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "rating centers must use START:STOP:STEP"
        ) from error
    if step <= 0 or stop < start:
        raise argparse.ArgumentTypeError("invalid rating center range")
    return list(range(start, stop + 1, step))


def read_contest_ids(training_file: Path) -> list[int]:
    contest_ids: list[int] = []
    seen: set[int] = set()
    with training_file.open("r", encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file):
            contest_id = int(row["contestId"])
            if contest_id not in seen:
                seen.add(contest_id)
                contest_ids.append(contest_id)
    return contest_ids


def main():
    parser = argparse.ArgumentParser(
        description="Build problem-level features from cached contest data."
    )
    parser.add_argument(
        "--training-file",
        type=Path,
        default=PROCESSED_DATA_DIR / "training_data.csv",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--rating-centers",
        type=parse_centers,
        default=parse_centers("800:3500:100"),
        help="Inclusive START:STOP:STEP reference ratings (default: 800:3500:100).",
    )
    parser.add_argument("--rating-window", type=int, default=100)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    contest_ids = read_contest_ids(args.training_file)
    if args.limit is not None:
        contest_ids = contest_ids[: args.limit]

    fetcher = CodeforcesFetcher()
    output_rows: list[dict] = []
    for position, contest_id in enumerate(contest_ids, start=1):
        print(f"[{position}/{len(contest_ids)}] Building contest {contest_id}...")
        standings = fetcher._make_request(
            "contest.standings", {"contestId": contest_id}
        )
        rating_changes = fetcher._make_request(
            "contest.ratingChanges", {"contestId": contest_id}
        )
        submissions = fetcher.get_all_contest_submissions(contest_id)
        output_rows.extend(
            build_contest_problem_features(
                contest_id=contest_id,
                contest=standings["contest"],
                problems=standings["problems"],
                rating_changes=rating_changes,
                submissions=submissions,
                centers=args.rating_centers,
                half_width=args.rating_window,
            )
        )

    if not output_rows:
        raise RuntimeError("no rated problem features were generated")

    output_path = args.output.resolve()
    ensure_directory(output_path.parent)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    temporary_path.replace(output_path)
    print(f"Wrote {len(output_rows)} problem rows to {output_path}")


if __name__ == "__main__":
    main()
