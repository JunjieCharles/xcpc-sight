"""Publish Shenyang and Jingzhou from eleven pinned local SRK inputs."""

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
from scripts.publish_leshan_2026_results import CONTEST_ID as LESHAN_ID
from scripts.publish_leshan_2026_results import INPUTS as PREVIOUS_INPUTS
from scripts.publish_leshan_2026_results import SHA256 as LESHAN_SHA256

INPUTS = (*PREVIOUS_INPUTS, (LESHAN_ID, "ccpc2026", LESHAN_SHA256))
RESULTS = (
    ("icpc2026shenyang", "icpc2026", "icpc-2026-shenyang", "115431517127405568",
     "71bf9079b565ffa843b945bd9bb90b53e53e2b8eefd3297c460f81c875dac1f5"),
    ("ccpc2026jingzhou", "ccpc2026", "ccpc-2026-jingzhou", "115429582852816896",
     "8a097d795d16bf05ffb541b17235997929e592d45d68850be74b55bc079b448c"),
)


def publish(input_dir: Path, previous_input_dir: Path, data_dir: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    normalizer = DefaultNormalizer(
        school_aliases=load_school_aliases(root / "config/school-aliases.json")
    )
    contests = []
    reviews = []
    specs = {cid: (pid, fid, sha) for cid, _, pid, fid, sha in RESULTS}
    for cid, collection, sha in (*INPUTS, *((c, s, h) for c, s, _, _, h in RESULTS)):
        directory = input_dir if cid in specs else previous_input_dir
        raw = (directory / f"{cid}.srk.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f"{cid}: SRK SHA-256 mismatch")
        payload = json.loads(raw)
        provenance = None
        if cid in specs:
            pid, fid, _ = specs[cid]
            url = f"https://cdn.algoux.cn/rankland/file/{fid}/{cid}.srk.json"
            provenance = ContestProvenance(cid, fid, url, sha)
        contest = normalize_srk_contest(
            payload, contest_uk=cid, series=collection, provenance=provenance,
        )
        contests.append(contest)
        if cid not in specs:
            continue
        preview = json.loads((data_dir / f"previews/{pid}.json").read_text(encoding="utf-8"))
        removed_path = root / f"config/review-removed-results/{cid}.json"
        removed = (
            json.loads(removed_path.read_text(encoding="utf-8")) if removed_path.exists() else {}
        )
        reviews.append(project_review_contest(
            preview, contest, normalizer=normalizer, removed_results=removed,
            result_medals=_history_medals(payload, contest.teams, cid),
        ))
    season = select_season(tuple(contests), SEASON_2026_2027)
    ratings = project_series_rating_data(
        calculate_series_ratings(season.contests),
        series_id="2026-2027", title="2026–2027 ICPC + CCPC",
    )
    review_path = data_dir / "reviews/2026-2027.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["contests"] = [c for c in review["contests"] if c["id"] not in specs] + reviews
    review["contests"].sort(key=lambda c: (
        c["startAt"][:10], not c["id"].startswith("icpc"), c["startAt"], c["id"],
    ))
    write_json_atomic(data_dir / "series/2026-2027.json", ratings)
    write_json_atomic(review_path, review)
    print(f"Published {len(ratings['competitors'])} competitors, {len(season.contests)} contests")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--previous-input-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("static/data"))
    args = parser.parse_args()
    publish(args.input_dir, args.previous_input_dir, args.data_dir)


if __name__ == "__main__":
    main()
