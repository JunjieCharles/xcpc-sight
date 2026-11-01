"""Publish Wuhan ratings and review from seven local, hash-verified SRK inputs.

The six earlier inputs are pinned by the October and Chengdu publishers.
Only the current season ratings and Wuhan review are updated.
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
from scripts.publish_chengdu_2026_results import CONTEST_ID as CHENGDU_ID
from scripts.publish_chengdu_2026_results import SHA256 as CHENGDU_SHA256
from scripts.publish_october_2026_results import INPUTS as OCTOBER_INPUTS

INPUTS = (*OCTOBER_INPUTS, (CHENGDU_ID, "icpc2026", CHENGDU_SHA256))

CONTEST_ID = "icpc2026wuhan"
FILE_ID = "110327570620391424"
SHA256 = "b72266f7fe737bb6cd2ed08d0e72e929a2c63b2404d067358a4bcd5b2488068a"
FILE_URL = f"https://cdn.algoux.cn/rankland/file/{FILE_ID}/{CONTEST_ID}.srk.json"


def publish(input_dir: Path, previous_input_dir: Path, data_dir: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    contests = []
    for contest_id, collection, sha in (*INPUTS, (CONTEST_ID, "icpc2026", SHA256)):
        directory = input_dir if contest_id == CONTEST_ID else previous_input_dir
        raw = (directory / f"{contest_id}.srk.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f"{contest_id}: SRK SHA-256 mismatch")
        payload = json.loads(raw)
        contest = normalize_srk_contest(
            payload, contest_uk=contest_id, series=collection,
            provenance=ContestProvenance(CONTEST_ID, FILE_ID, FILE_URL, SHA256)
            if contest_id == CONTEST_ID else None,
        )
        contests.append(contest)

    preview = json.loads(
        (data_dir / "previews/icpc-2026-wuhan.json").read_text(encoding="utf-8")
    )
    result = project_review_contest(
        preview, contests[-1],
        normalizer=DefaultNormalizer(
            school_aliases=load_school_aliases(root / "config/school-aliases.json")
        ),
        result_medals=_history_medals(payload, contests[-1].teams, CONTEST_ID),
    )
    season = select_season(tuple(contests), SEASON_2026_2027)
    ratings = project_series_rating_data(
        calculate_series_ratings(season.contests),
        series_id="2026-2027", title="2026–2027 ICPC + CCPC",
    )
    review_path = data_dir / "reviews/2026-2027.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["contests"] = [c for c in review["contests"] if c["id"] != CONTEST_ID] + [result]
    review["contests"].sort(key=lambda c: (
        c["startAt"][:10], not c["id"].startswith("icpc"), c["startAt"], c["id"],
    ))
    write_json_atomic(data_dir / "series/2026-2027.json", ratings)
    write_json_atomic(review_path, review)
    print(f"Published {len(ratings['competitors'])} competitors, "
          f"{len(season.contests)} contests, {len(result['teams'])} Wuhan review teams")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--previous-input-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("static/data"))
    args = parser.parse_args()
    publish(args.input_dir, args.previous_input_dir, args.data_dir)


if __name__ == "__main__":
    main()
