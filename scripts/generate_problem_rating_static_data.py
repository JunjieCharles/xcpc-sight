from __future__ import annotations

import argparse
import csv
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.errors import DataValidationError
from problem_rating import (
    ProblemRatingRecord,
    project_problem_rating_index,
    project_problem_rating_series,
)

SUPPORTED_SERIES = frozenset({"2025-2026", "nowcoder-summer-2026", "hdu-summer-2026"})
REQUIRED_COLUMNS = (
    "series",
    "nativeContestId",
    "contestName",
    "problemIndex",
    "problemName",
    "solvedCount",
    "participantCount",
    "timeSampleCount",
    "predictedRating",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate static problem-rating JSON from an offline prediction CSV."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data-cache/problem-rating/outputs/analysis/xcpc_problem_ratings.csv"),
    )
    parser.add_argument(
        "--rating-data-dir",
        type=Path,
        default=Path("static/data"),
        help="directory containing the participant-rating index and series JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("static/data/problem-rating"),
    )
    return parser.parse_args()


def _parse_integer(row: Mapping[str, str], column: str, row_number: int) -> int:
    value = row.get(column, "")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise DataValidationError(
            f"prediction CSV row {row_number}, column {column}: expected integer"
        ) from error


def read_prediction_csv(input_path: Path) -> list[ProblemRatingRecord]:
    try:
        input_file = input_path.open(encoding="utf-8-sig", newline="")
    except OSError as error:
        raise DataValidationError(f"unable to read prediction CSV {input_path}") from error
    with input_file:
        reader = csv.DictReader(input_file)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or ())]
        if missing:
            raise DataValidationError(f"prediction CSV {input_path}: missing columns {missing}")
        records = []
        for row_number, row in enumerate(reader, start=2):
            records.append(
                ProblemRatingRecord(
                    series_id=row["series"],
                    native_contest_id=row["nativeContestId"],
                    contest_name=row["contestName"],
                    problem_index=row["problemIndex"],
                    problem_name=row["problemName"],
                    solved_count=_parse_integer(row, "solvedCount", row_number),
                    participant_count=_parse_integer(row, "participantCount", row_number),
                    time_sample_count=_parse_integer(row, "timeSampleCount", row_number),
                    predicted_rating=_parse_integer(row, "predictedRating", row_number),
                )
            )
    if not records:
        raise DataValidationError(f"prediction CSV {input_path}: no records")
    unknown = sorted({record.series_id for record in records} - SUPPORTED_SERIES)
    if unknown:
        raise DataValidationError(f"prediction CSV contains unsupported series {unknown}")
    return records


def _read_json(path: Path) -> Mapping[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataValidationError(f"unable to read JSON document {path}") from error
    if not isinstance(document, Mapping):
        raise DataValidationError(f"JSON document {path} must be an object")
    return document


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


def generate_problem_rating_static_data(
    input_csv: Path,
    rating_data_dir: Path,
    output_dir: Path,
) -> None:
    records = read_prediction_csv(input_csv)
    records_by_series = {
        series_id: [record for record in records if record.series_id == series_id]
        for series_id in SUPPORTED_SERIES
    }
    rating_index = _read_json(rating_data_dir / "index.json")
    raw_entries = rating_index.get("series")
    if not isinstance(raw_entries, list):
        raise DataValidationError("participant-rating index.series must be a list")

    publications: list[tuple[dict[str, object], str]] = []
    found: set[str] = set()
    for entry_index, entry in enumerate(raw_entries):
        if not isinstance(entry, Mapping):
            raise DataValidationError(
                f"participant-rating index.series[{entry_index}] must be an object"
            )
        series_id = entry.get("id")
        if series_id not in SUPPORTED_SERIES:
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise DataValidationError(f"series {series_id}: path must be non-empty")
        rating_series = _read_json(rating_data_dir / path)
        document = project_problem_rating_series(records_by_series[series_id], rating_series)
        publications.append((document, f"series/{series_id}.json"))
        found.add(series_id)

    missing = sorted(SUPPORTED_SERIES - found)
    if missing:
        raise DataValidationError(f"participant-rating index is missing supported series {missing}")
    index = project_problem_rating_index(publications)
    for document, path in publications:
        write_json_atomic(output_dir / path, document)
    write_json_atomic(output_dir / "index.json", index)


def main() -> int:
    args = parse_args()
    generate_problem_rating_static_data(
        args.input_csv,
        args.rating_data_dir,
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
