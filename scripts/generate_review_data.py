"""Publish a pinned result snapshot without refreshing pre-contest metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx
from generate_static_data import write_json_atomic

from core import ContestProvenance, DefaultNormalizer, load_school_aliases, normalize_srk_contest
from core.review import project_review_contest

FILE_ID = "90036200580141056"
SHA256 = "39077e4904169b353f85c4484efa5fe9064727ba00cf6685661270d5d9bf7575"
FILE_URL = f"https://cdn.algoux.cn/rankland/file/{FILE_ID}/icpc2026preliminary-1.srk.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, default=Path("static/data/previews/2026-2027.json"))
    parser.add_argument(
        "--srk", type=Path, help="local SRK; omit to download the pinned first contest"
    )
    parser.add_argument("--contest-id", default="icpc2026preliminary-1")
    parser.add_argument("--file-id", default=FILE_ID)
    parser.add_argument("--file-url", default=FILE_URL)
    parser.add_argument("--sha256", default=SHA256)
    parser.add_argument(
        "--school-aliases", type=Path,
        default=Path(__file__).resolve().parents[1] / "config/school-aliases.json",
    )
    parser.add_argument(
        "--overrides", type=Path, help="JSON mapping preview team ID to result team ID"
    )
    parser.add_argument("--output", type=Path, default=Path("static/data/reviews/2026-2027.json"))
    args = parser.parse_args()
    if args.srk:
        raw = args.srk.read_bytes()
    else:
        response = httpx.get(args.file_url, follow_redirects=True, timeout=60)
        response.raise_for_status()
        raw = response.content
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError(f"contest {args.contest_id}: SRK SHA-256 mismatch")
    preview = json.loads(args.preview.read_text(encoding="utf-8"))
    contest = normalize_srk_contest(
        json.loads(raw),
        contest_uk=args.contest_id,
        series=preview["seriesId"],
        provenance=ContestProvenance(args.contest_id, args.file_id, args.file_url, args.sha256),
    )
    aliases = load_school_aliases(args.school_aliases)
    overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides else {}
    projected = project_review_contest(
        preview,
        contest,
        normalizer=DefaultNormalizer(school_aliases=aliases),
        overrides=overrides,
    )
    document = {"schemaVersion": 1, "seriesId": preview["seriesId"], "contests": []}
    if args.output.exists():
        document = json.loads(args.output.read_text(encoding="utf-8"))
        if document["schemaVersion"] != 1 or document["seriesId"] != preview["seriesId"]:
            raise ValueError("output belongs to a different schema or series")
    document["contests"] = [c for c in document["contests"] if c["id"] != projected["id"]]
    document["contests"].append(projected)
    document["contests"].sort(key=lambda c: (c["startAt"], c["id"]))
    write_json_atomic(args.output, document)
    print(f"Published {len(projected['teams'])} teams to {args.output}")


if __name__ == "__main__":
    main()
