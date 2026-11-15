"""Published November 15 previews: identities, fresh sources and season matching."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.generate_preview_data import PersonIndex, PersonRecord, load_normalizer
from scripts.preview_roster import attach_online_ranks, online_rank_index

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "static/data"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_added_teams_use_frozen_ratings_and_preserve_all_original_teams():
    expected = read(ROOT / "tests/fixtures/review/november-15-preview-backfill.json")
    reviews = read(DATA / "reviews/2026-2027.json")
    for pid, baseline in expected.items():
        p = read(DATA / f"previews/{pid}.json")
        n = baseline.get("retainedOriginalTeamCount", baseline["originalTeamCount"])
        digest = hashlib.sha256(json.dumps(p["teams"][:n], ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
        assert digest == baseline["originalTeamsSha256"]
        assert p["rosterSupplement"]["ratingSnapshotDate"] == "2026-11-09"
        assert [{"school": t["school"], "name": m["name"], "ratings": m["ratings"]}
                for t in p["teams"][n:] for m in t["members"]] == baseline["addedMembers"]
        c = next(c for c in reviews["contests"] if c["previewId"] == pid)
        added = {t["id"] for t in p["teams"][n:]}
        assert added == set(p["rosterSupplement"]["previewTeamIds"])
        assert {t["resultTeamId"] for t in c["teams"] if t["previewTeamId"] in added} == (
            set(p["rosterSupplement"]["resultTeamIds"]))
        assert all(t["hasActivity"] for t in c["teams"] if t["previewTeamId"] in added)


@pytest.mark.parametrize("cid,total,official,members,history", [
    ("icpc-2026-shenyang", 416, 401, 1248, 412),
    ("ccpc-2026-jingzhou", 321, 300, 960, 409),
])
def test_latest_complete_previews(cid, total, official, members, history):
    p = read(DATA / f"previews/{cid}.json")
    roster = read(DATA / f"rosters/{cid}.json")
    assert p["snapshotDate"] == "2026-11-09"
    assert len(p["teams"]) == total
    assert sum(not t["excluded"] for t in p["teams"]) == official
    assert p["matchingSummary"]["members"] == members
    assert len({t["id"] for t in p["teams"]}) == total
    assert not p.get("onlineRanksOnly", False)
    assert p["powerMetrics"] == ["xcpcrating", "xcpcElo", "currentSeason", "onlineRanks"]
    assert p["sourceSnapshots"]["xcpcrating"] == "2026-11-08T18:05:59.759128+00:00"
    assert p["sourceSnapshots"]["xcpcElo"] == "2026-11-09T03:50:23.987Z"
    assert p["sourceSnapshots"]["currentSeason"] == "2026-11-08T09:30:00+08:00"
    assert p["sourcesFetchedAt"] == "2026-11-09T03:55:32.169599+00:00"
    build = p["sourceBuilds"]["xcpcElo"]
    assert build["codeCommit"] == "039a15a41998edd1c7d7b61c97c8d9b319dbb8a7"
    assert build["srkCommit"] == "0f24f2c7801e068d85caebbf51af305669fd5a84"
    assert (build["contests"], build["players"]) == (195, 68349)
    assert build["includedContestIds"] == ["ccpc2026leshan", "icpc2026nanjing"]
    assert build["generatedAt"] == p["sourceSnapshots"]["xcpcElo"]
    assert p["medalSources"]["addedContestIds"] == []
    assert p["medalSources"]["cpcfinderCoveredContestIds"] == [
        "ccpc2026changchun", "ccpc2026leshan", "icpc2026chengdu", "icpc2026nanjing",
        "icpc2026wuhan", "icpc2026xi_an",
    ]
    normalizer = load_normalizer(ROOT / "config/school-aliases.json")
    series_path = DATA / "series/2026-2027.json"
    series = read(series_path)
    cutoff = datetime.fromisoformat(p["sourceSnapshots"]["currentSeason"])
    records = []
    for person in series["competitors"]:
        prior = [h for h in person["participations"] if datetime.fromisoformat(
            series["contests"][h["contestIndex"]]["startAt"]) <= cutoff]
        if prior:
            records.append(PersonRecord(person["member"], person["school"], prior[-1]["after"]))
    index = PersonIndex(records, normalizer)
    projected = json.loads(json.dumps(p["teams"]))
    attach_online_ranks(projected, online_rank_index(read(series_path), normalizer, p["sortAt"]),
                        normalizer)
    assert projected == p["teams"]
    for row, team in zip(roster["teams"], p["teams"], strict=True):
        assert row == {"school": team["school"], "name": team["name"],
                       "members": [m["name"] for m in team["members"]],
                       "excluded": team["excluded"]}
        for member in team["members"]:
            match = index.match(member["name"], team["school"])
            assert member["ratings"]["currentSeason"] == (match.rating if match else None)
        for record in team["currentSeasonHistory"] + team["previousSeasonHistory"]:
            assert "ladies" not in record["contestId"]
            assert "invitational" not in record["contestId"]
            assert datetime.fromisoformat(record["startAt"]) < datetime.fromisoformat(p["sortAt"])
    assert sum(len(t["currentSeasonHistory"]) for t in p["teams"]) == history
    assert {"ccpc2026leshan", "icpc2026nanjing"} <= {
        h["contestId"] for t in p["teams"] for h in t["currentSeasonHistory"]}
    for source in p["metricSources"]:
        assert datetime.fromisoformat(p["sourceSnapshots"][source["id"]]) < (
            datetime.fromisoformat(p["sortAt"]))
        assert sum(m["ratings"][source["id"]] is not None
                   for t in p["teams"] for m in t["members"]) == (
                       p["matchingSummary"][source["id"]])


def test_jingzhou_manual_identity_and_schedule():
    roster = read(DATA / "rosters/ccpc-2026-jingzhou.json")
    p = read(DATA / "previews/ccpc-2026-jingzhou.json")
    source = roster["source"]
    assert hashlib.sha256((ROOT / "static/sources/ccpc-2026-jingzhou-manual.pdf").read_bytes()
                          ).hexdigest() == source["sha256"] == (
        "9d6044dd552c4834fdb3988e61bb8b77429b74987f2b94affaffd95f988b88e4")
    digest = hashlib.sha256(json.dumps(roster["teams"], ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest()
    assert digest == source["identitySha256"] == (
        "9baef99e3b49aa8c7b146114d10ebbdd13182beab93b1f526a57c429b929b0db")
    assert source["originalIdentitySha256"] == (
        "81f99fa3a09b18eaa600c01ce3d69fc20919de6423fa00e5e230a16d5309a293")
    assert source["pdfPages"] == [23, 31]
    assert p["teamSource"]["url"] == source["url"]
    assert "临时版" in p["teamSource"]["title"]
    assert p["hostSchool"] == "长江大学"
    assert p["sortAt"] == "2026-11-15T09:30:00+08:00"
    assert p["endAt"] == "2026-11-15T14:30:00+08:00"
    assert roster["teams"][222]["members"] == ["林泽宇", "魏子安"]
    assert not any(t["id"] == "t_260fc04dc78d66ccda61" for t in p["teams"])
    assert not any(t["school"] == "贵州大学" and t["name"] == "贵大2对"
                   for t in roster["teams"])
    assert p["rosterSupplement"]["removedPreviewTeamIds"] == ["t_260fc04dc78d66ccda61"]
    assert not (ROOT / "config/review-removed-results/ccpc2026jingzhou.json").exists()
