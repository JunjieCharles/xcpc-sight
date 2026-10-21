"""Publish the two pinned October 18 results from local, hash-verified SRK files.

Download the five inputs specified in INPUTS into --input-dir first. This command
does not refresh pre-contest snapshots or access the network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core import (
    SEASON_2026_2027,
    ContestProvenance,
    DefaultNormalizer,
    load_school_aliases,
    normalize_srk_contest,
    project_review_contest,
    select_season,
)
from rating import calculate_series_ratings, project_series_rating_data
from scripts.generate_static_data import write_json_atomic
from scripts.preview_history import _history_medals

REGIONAL_FILE_IDS = {
    "ccpc2026changchun": "105706787390464000",
    "icpc2026xi_an": "105318714861256704",
}
INPUTS = (
    ("icpc2026preliminary-1", "icpc2026",
     "8ca3ddf111c255b352021678000f4bac0040aa3e3f2cd827fd2fdc260f0dbd0b"),
    ("icpc2026preliminary-2", "icpc2026",
     "a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9"),
    ("ccpc2026preliminary", "ccpc2026",
     "d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1"),
    ("ccpc2026changchun", "ccpc2026",
     "a430faa32608ae0812674333c8ff752691da3927a56a9b58b0aa0a57e6c583a2"),
    ("icpc2026xi_an", "icpc2026",
     "ac458e941d11d0b235c5e5f68d286592d0c5897bf50b96d8fd75f81ba050945e"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("static/data"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    normalizer = DefaultNormalizer(
        school_aliases=load_school_aliases(root / "config/school-aliases.json")
    )
    contests = []
    review_path = args.data_dir / "reviews/2026-2027.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    for contest_id, collection, sha in INPUTS:
        raw = (args.input_dir / f"{contest_id}.srk.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f"{contest_id}: SRK SHA-256 mismatch")
        payload = json.loads(raw)
        file_id = REGIONAL_FILE_IDS.get(contest_id)
        url = f"https://cdn.algoux.cn/rankland/file/{file_id}/{contest_id}.srk.json"
        contest = normalize_srk_contest(
            payload, contest_uk=contest_id, series=collection,
            provenance=ContestProvenance(contest_id, file_id, url, sha) if file_id else None,
        )
        contests.append(contest)
        if "preliminary" in contest_id:
            continue
        preview_id = "icpc-2026-xian" if collection == "icpc2026" else "ccpc-2026-changchun"
        preview = json.loads(
            (args.data_dir / f"previews/{preview_id}.json").read_text(encoding="utf-8")
        )
        mappings = {}
        for parameter, directory in [("overrides", "review-overrides"),
                                     ("unofficial_results", "review-unofficial-results")]:
            path = root / "config" / directory / f"{contest_id}.json"
            mappings[parameter] = (
                json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            )

        result = project_review_contest(
            preview, contest,
            normalizer=normalizer,
            result_medals=_history_medals(payload, contest.teams, contest_id),
            **mappings,
        )
        review["contests"] = [c for c in review["contests"] if c["id"] != contest_id] + [result]
        print(f"{contest_id}: {len(result['teams'])} preview results")
    season = select_season(tuple(contests), SEASON_2026_2027)
    ratings = project_series_rating_data(calculate_series_ratings(season.contests),
                                        series_id="2026-2027", title="2026–2027 ICPC + CCPC")
    review["contests"].sort(key=lambda c: (c["startAt"][:10],
                                         not c["id"].startswith("icpc"), c["startAt"], c["id"]))
    write_json_atomic(args.data_dir / "series/2026-2027.json", ratings)
    write_json_atomic(review_path, review)
    print(f"Published {len(ratings['competitors'])} competitors "
          f"across {len(season.contests)} contests")


if __name__ == "__main__":
    main()
