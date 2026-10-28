"""Supplement CPC Finder medal snapshots with verified pre-contest season results."""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core import DefaultNormalizer
from scripts.preview_history import build_history_index

MEDALS = ("gold", "silver", "bronze")


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result if result.tzinfo else result.replace(tzinfo=ZoneInfo("Asia/Shanghai"))


def eligible_contests(series: dict, preview: dict) -> list[dict]:
    if series["id"] != preview["seriesId"]:
        raise ValueError("medals: series must match the preview season")
    return [c for c in series["contests"] if "preliminary" not in c["id"]
            and instant(c["startAt"]) < instant(preview["sortAt"])]


def supplement_medals(preview: dict, contests: list[dict], history: dict,
                      normalizer: DefaultNormalizer, covered_ids: list[str] | None = None) -> dict:
    """Return a new snapshot; repeated application replaces the previous supplement.

    covered_ids explicitly lists contests already included in CPC Finder. Without
    it, the baseline must predate every eligible medal contest; timestamps alone
    cannot establish whether a newer CPC Finder snapshot includes a result.
    """
    eligible = [c for c in contests if "preliminary" not in c["id"]
                and instant(c["startAt"]) < instant(preview["sortAt"])]
    ids = {c["id"] for c in eligible}
    baseline = preview["sourceSnapshots"]["cpcfinder"]
    if instant(baseline) >= instant(preview["sortAt"]):
        raise ValueError("medals: CPC Finder snapshot must precede the preview")
    previous = preview.get("medalSources")
    if previous and previous["cpcfinderSnapshot"] != baseline:
        raise ValueError("medals: CPC Finder baseline changed; regenerate the preview first")
    if covered_ids is None and previous:
        covered_ids = previous["cpcfinderCoveredContestIds"]
    if covered_ids is None:
        if any(instant(c["startAt"]) <= instant(baseline) for c in eligible):
            raise ValueError("medals: specify cpcfinder-covered-contests to avoid double counting")
        covered_ids = []
    covered = set(covered_ids)
    if len(covered) != len(covered_ids) or not covered <= ids:
        raise ValueError("medals: covered contests must be unique eligible contest IDs")
    if any(instant(c["startAt"]) > instant(baseline) for c in eligible if c["id"] in covered):
        raise ValueError("medals: covered contest follows CPC Finder snapshot")
    added = ids - covered
    document = copy.deepcopy(preview)
    if not eligible and not previous:
        return document
    for team in document["teams"]:
        totals = dict.fromkeys(MEDALS, 0)
        for member in team["members"]:
            key = (normalizer.member(member["name"]), normalizer.school(team["school"]))
            # An unmatched CPC Finder member has no cumulative baseline, even
            # when that service has already imported the contest for others.
            member_ids = (ids if member.get("ratings", {}).get("cpcfinder", 0) is None
                          else added)
            # Same normalized identity can occur in multiple upstream rows. Like
            # season ratings, count the best official result once per contest.
            best = {}
            for record in history.get(key, []):
                cid = record["contestId"]
                if cid not in member_ids:
                    continue
                if cid not in best or (record["rank"], record["teamId"]) < (
                        best[cid]["rank"], best[cid]["teamId"]):
                    best[cid] = record
            supplement = {m: sum(r["medal"] == m for r in best.values()) for m in MEDALS}
            old = member.get("medalSupplement", dict.fromkeys(MEDALS, 0))
            baseline_counts = {}
            for medal in MEDALS:
                value, delta = member["medals"][medal], old[medal]
                if type(value) is not int or type(delta) is not int or not 0 <= delta <= value:
                    raise ValueError(f"medals: invalid baseline for {key}: {medal}")
                baseline_counts[medal] = value - delta
            member["medalSupplement"] = supplement
            member["medals"] = {m: baseline_counts[m] + supplement[m] for m in MEDALS}
            for medal in MEDALS:
                totals[medal] += member["medals"][medal]
        team["medals"] = totals
    document["medalSources"] = {
        "cpcfinderSnapshot": baseline,
        "cpcfinderCoveredContestIds": sorted(covered),
        "addedContestIds": sorted(added),
    }
    return document


def add_current_medals(preview: dict, series: dict, root: Path | None,
                       normalizer: DefaultNormalizer, covered_ids: list[str] | None = None) -> dict:
    contests = eligible_contests(series, preview)
    if contests and root is None:
        raise ValueError("medals: --current-history-srk-root required for prior regional results")
    history = (build_history_index({**series, "contests": contests}, root, normalizer)
               if contests else {})
    return supplement_medals(preview, contests, history, normalizer, covered_ids)


def main() -> None:
    from scripts.generate_preview_data import load_normalizer, write_json_atomic

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", type=Path, required=True)
    parser.add_argument("--srk-root", type=Path, required=True)
    parser.add_argument("--preview", type=Path, action="append", required=True)
    parser.add_argument("--cpcfinder-covered-contests", nargs="*", default=None)
    args = parser.parse_args()
    normalizer = load_normalizer(Path(__file__).resolve().parents[1] / "config/school-aliases.json")
    series = json.loads(args.series.read_text(encoding="utf-8"))
    outputs = []
    for path in args.preview:
        original = json.loads(path.read_text(encoding="utf-8"))
        document = add_current_medals(original, series, args.srk_root, normalizer,
                                      args.cpcfinder_covered_contests)
        if document != original:
            outputs.append((path, document))
    for path, document in outputs:
        write_json_atomic(path, document)


if __name__ == "__main__":
    main()
