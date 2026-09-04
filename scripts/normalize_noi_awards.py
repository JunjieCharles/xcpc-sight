from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from core import parse_noi_awards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize cached official NOI award-list tables into dataset documents"
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data-cache/noi"))
    parser.add_argument("--output-dir", type=Path, default=Path("data-cache/noi/normalized"))
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


def build_documents(input_dir: Path) -> tuple[dict[str, object], dict[int, dict[str, object]]]:
    sources = load_json(input_dir / "sources.json")
    years = sources.get("years")
    if not isinstance(years, dict) or not years:
        raise ValueError(f"{input_dir / 'sources.json'}: expected non-empty years object")

    documents: dict[int, dict[str, object]] = {}
    index_years = []
    for text_year, source in sorted(years.items(), key=lambda item: int(item[0])):
        year = int(text_year)
        if not isinstance(source, dict) or not isinstance(source.get("cache_file"), str):
            raise ValueError(f"NOI {year}: missing cache_file in sources index")
        if not isinstance(source.get("source_url"), str):
            raise ValueError(f"NOI {year}: missing source_url in sources index")
        rows = load_json(input_dir / source["cache_file"])
        if not isinstance(rows, list):
            raise ValueError(f"NOI {year}: expected table rows")
        awards = [award.to_document() for award in parse_noi_awards(year, rows)]
        documents[year] = {"schemaVersion": 1, "year": year, "awards": awards}
        index_years.append(
            {"year": year, "path": f"{year}.json", "sourceUrl": source["source_url"]}
        )
    return {"schemaVersion": 1, "years": index_years}, documents


def main() -> None:
    args = parse_args()
    index, documents = build_documents(args.input_dir)
    for year, document in documents.items():
        write_json_atomic(args.output_dir / f"{year}.json", document)
    write_json_atomic(args.output_dir / "index.json", index)


if __name__ == "__main__":
    main()